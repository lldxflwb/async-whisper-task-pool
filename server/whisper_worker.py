import asyncio
import logging
import os
import tempfile
import shutil
import subprocess
import json
from typing import Optional
from datetime import datetime
# 移除whisper导入，改用命令行调用
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
        # 不再需要在内存中加载模型
        self._current_model_name = None
    
    async def start(self):
        """启动工作器"""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        # 验证whisper命令是否可用
        if not await self._check_whisper_available():
            raise RuntimeError("Whisper command not available")
        
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
        
        # 清理模型引用
        self._current_model_name = None
        logger.info("Whisper worker stopped")
    
    async def _check_whisper_available(self) -> bool:
        """检查whisper命令是否可用"""
        try:
            process = await asyncio.create_subprocess_exec(
                'whisper', '--help',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            return process.returncode == 0
        except Exception as e:
            logger.error(f"Whisper command not available: {e}")
            return False
    
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
            
            # 创建临时目录用于输出
            with tempfile.TemporaryDirectory() as temp_output_dir:
                # 构建whisper命令
                cmd = [
                    'whisper',
                    audio_path,
                    '--model', model,
                    '--output_format', 'srt',
                    '--output_dir', temp_output_dir,
                ]
                
                logger.info(f"Running whisper command: {' '.join(cmd)}")
                
                # 在进程中执行whisper命令
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                    logger.error(f"Whisper command failed: {error_msg}")
                    raise RuntimeError(f"Whisper command failed: {error_msg}")
                
                # 查找生成的SRT文件
                srt_file = None
                for file in os.listdir(temp_output_dir):
                    if file.endswith('.srt'):
                        srt_file = os.path.join(temp_output_dir, file)
                        break
                
                if not srt_file or not os.path.exists(srt_file):
                    raise RuntimeError("SRT file not generated")
                
                # 读取SRT内容
                with open(srt_file, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
                
                logger.info(f"Transcription completed, SRT length: {len(srt_content)} characters")
                return srt_content
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查工作器是否运行
            if not self.is_running:
                return False
            
            # 检查whisper命令是否可用
            if not await self._check_whisper_available():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取工作器状态"""
        return {
            "is_running": self.is_running,
            "whisper_available": True,  # 需要异步检查，这里简化
            "current_model": self._current_model_name,
            "worker_task_running": self._worker_task is not None and not self._worker_task.done()
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