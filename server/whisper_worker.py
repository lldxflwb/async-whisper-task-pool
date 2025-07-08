import asyncio
import logging
import subprocess
import os
import tempfile
import shutil
from typing import Optional
from datetime import datetime
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
    
    async def start(self):
        """启动工作器"""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        self.is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Whisper worker started")
    
    async def stop(self):
        """停止工作器"""
        if not self.is_running:
            return
        
        self.is_running = False
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
        """使用Whisper转录音频"""
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
            
            # 创建临时输出目录
            with tempfile.TemporaryDirectory() as temp_output_dir:
                # 构建Whisper命令
                # 直接使用用户提供的模型名称
                cmd = [
                    "whisper",
                    audio_path,
                    "--model", model,
                    "--output_dir", temp_output_dir,
                    "--output_format", "srt",
                    "--verbose", "True"    # 增加详细输出
                ]
                
                logger.info(f"Executing command: {' '.join(cmd)}")
                
                # 执行Whisper命令
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # 记录输出信息
                if stdout:
                    logger.info(f"Whisper stdout: {stdout.decode()}")
                if stderr:
                    logger.info(f"Whisper stderr: {stderr.decode()}")
                
                if process.returncode != 0:
                    error_msg = f"Whisper command failed with return code {process.returncode}"
                    if stderr:
                        error_msg += f"\nStderr: {stderr.decode()}"
                    raise RuntimeError(error_msg)
                
                # 列出输出目录中的所有文件
                output_files = os.listdir(temp_output_dir)
                logger.info(f"Files in output directory: {output_files}")
                
                # 查找生成的SRT文件
                srt_file = None
                for file in output_files:
                    if file.endswith('.srt'):
                        srt_file = os.path.join(temp_output_dir, file)
                        break
                
                if not srt_file:
                    raise FileNotFoundError(f"No SRT file generated by Whisper. Available files: {output_files}")
                
                # 读取SRT内容
                with open(srt_file, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
                
                logger.info(f"Transcription completed, SRT length: {len(srt_content)} characters")
                return srt_content
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def _check_whisper_installation(self) -> bool:
        """检查Whisper是否正确安装"""
        try:
            process = await asyncio.create_subprocess_exec(
                "whisper", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode == 0
            
        except FileNotFoundError:
            logger.error("Whisper command not found. Please install openai-whisper")
            return False
        except Exception as e:
            logger.error(f"Error checking Whisper installation: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查工作器是否运行
            if not self.is_running:
                return False
            
            # 检查Whisper是否可用
            whisper_ok = await self._check_whisper_installation()
            if not whisper_ok:
                return False
            
            # 检查必要的目录是否存在
            for dir_path in [config.UPLOAD_DIR, config.RESULT_DIR, config.TEMP_DIR]:
                if not os.path.exists(dir_path):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取工作器状态"""
        return {
            "is_running": self.is_running,
            "task_info": self._worker_task is not None and not self._worker_task.done()
        }

# 全局工作器实例
whisper_worker = WhisperWorker()

async def start_worker():
    """启动工作器"""
    await whisper_worker.start()

async def stop_worker():
    """停止工作器"""
    await whisper_worker.stop()

async def worker_health_check() -> bool:
    """工作器健康检查"""
    return await whisper_worker.health_check() 