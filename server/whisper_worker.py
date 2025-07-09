import asyncio
import logging
import os
import tempfile
import shutil
import subprocess
from typing import Optional
from datetime import datetime
import torch
from models import Task, TaskStatus
from task_manager import task_manager
from utils import ZipFileHandler, FileManager
from config import config

logger = logging.getLogger(__name__)

class WhisperWorker:
    """Whisper转录工作器"""
    
    def __init__(self):
        self.is_running = False
        self._worker_task = None
        # 设置CPU线程数
        self._setup_cpu_threads()
    
    def _setup_cpu_threads(self):
        """设置CPU线程数"""
        cpu_threads = config.WHISPER_CPU_THREADS
        logger.info(f"Setting PyTorch CPU threads to: {cpu_threads}")
        
        # 设置PyTorch线程数
        torch.set_num_threads(cpu_threads)
        
        # 设置OpenMP线程数（用于numpy等库）
        os.environ['OMP_NUM_THREADS'] = str(cpu_threads)
        
        # 设置MKL线程数（Intel Math Kernel Library）
        os.environ['MKL_NUM_THREADS'] = str(cpu_threads)
        
        logger.info(f"CPU threads configured: PyTorch={torch.get_num_threads()}, "
                   f"OMP={os.environ.get('OMP_NUM_THREADS')}, "
                   f"MKL={os.environ.get('MKL_NUM_THREADS')}")
    
    async def start(self):
        """启动工作器"""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        logger.info("Starting Whisper worker...")
        self.is_running = True
        
        # 启动工作器循环
        self._worker_task = asyncio.create_task(self._worker_loop())
        
        logger.info("Whisper worker started")
    
    async def stop(self):
        """停止工作器"""
        if not self.is_running:
            logger.warning("Worker is not running")
            return
        
        logger.info("Stopping Whisper worker...")
        self.is_running = False
        
        # 取消工作器任务
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Whisper worker stopped")
    
    async def _worker_loop(self):
        """工作器主循环"""
        logger.info("Worker loop started")
        
        while self.is_running:
            try:
                # 获取下一个任务
                task = task_manager.get_next_task()
                if task:
                    await self._process_task(task)
                else:
                    # 没有任务时等待
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(5)  # 发生错误时等待5秒
    
    async def _process_task(self, task: Task):
        """处理单个任务"""
        logger.info(f"Processing task: {task.id}")
        temp_dir = None
        
        try:
            # 检查任务状态
            if task.status != TaskStatus.PROCESSING:
                logger.warning(f"Task {task.id} is not in processing state")
                return
            
            # 解压任务ZIP文件
            if not task.zip_file_path or not os.path.exists(task.zip_file_path):
                raise FileNotFoundError(f"Task zip file not found: {task.zip_file_path}")
            
            extracted_data = ZipFileHandler.extract_task_zip(
                task.zip_file_path, 
                task.metadata.password
            )
            
            audio_path = extracted_data['audio_path']
            temp_dir = extracted_data['extract_dir']
            
            # 使用指定的模型转录音频
            model = task.metadata.model or config.WHISPER_MODEL
            srt_content = await self._transcribe_audio(audio_path, model)
            
            # 完成任务
            task_manager.complete_task(task.id, srt_content)
            
        except Exception as e:
            logger.error(f"Failed to process task {task.id}: {e}")
            task_manager.fail_task(task.id, str(e))
        finally:
            # 清理临时目录（解压后的文件）
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temp dir: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
            
            # 注意：ZIP文件的清理由task_manager处理
    
    async def _transcribe_audio(self, audio_path: str, model: str) -> str:
        """使用Whisper命令行转录音频"""
        logger.info(f"Transcribing audio: {audio_path} with model: {model}")
        
        try:
            # 检查音频文件是否存在
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # 检查音频文件大小
            file_size = os.path.getsize(audio_path)
            logger.info(f"Audio file size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError("Audio file is empty")
            
            # 准备输出目录
            output_dir = os.path.dirname(audio_path)
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            srt_path = os.path.join(output_dir, f"{audio_name}.srt")
            
            # 构建whisper命令行参数
            cmd = [
                "whisper",
                audio_path,
                "--model", model,
                "--threads", str(config.WHISPER_CPU_THREADS),
                "--output_format", "srt",
                "--output_dir", output_dir,
                "--verbose", "False"
            ]
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            logger.info(f"Using CPU threads: {config.WHISPER_CPU_THREADS}")
            
            # 在线程池中执行命令行，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    check=True,
                    cwd=output_dir
                )
            )
            
            logger.info(f"Whisper command completed. Return code: {result.returncode}")
            if result.stdout:
                logger.info(f"Whisper stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"Whisper stderr: {result.stderr}")
            
            # 读取生成的SRT文件
            if not os.path.exists(srt_path):
                raise FileNotFoundError(f"Expected SRT file not found: {srt_path}")
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # 清理生成的SRT文件（可选，取决于你是否想保留）
            try:
                os.remove(srt_path)
                logger.info(f"Cleaned up SRT file: {srt_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup SRT file: {e}")
            
            logger.info(f"Transcription completed, SRT length: {len(srt_content)} characters")
            return srt_content
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Whisper command failed: {e}")
            logger.error(f"Command stdout: {e.stdout}")
            logger.error(f"Command stderr: {e.stderr}")
            raise RuntimeError(f"Whisper transcription failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查工作器是否运行
            if not self.is_running:
                return False
            
            # 由于现在使用命令行，不再需要检查模型加载状态
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取工作器状态"""
        return {
            "is_running": self.is_running,
            "worker_task_running": self._worker_task is not None and not self._worker_task.done(),
            "cpu_threads": torch.get_num_threads(),
            "transcription_method": "command_line"
        }

# 全局工作器实例
worker = WhisperWorker()

async def start_worker():
    """启动工作器"""
    await worker.start()

async def stop_worker():
    """停止工作器"""
    await worker.stop()

async def worker_health_check() -> bool:
    """工作器健康检查"""
    return await worker.health_check() 