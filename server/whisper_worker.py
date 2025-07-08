import asyncio
import logging
import os
import tempfile
import shutil
from typing import Optional
from datetime import datetime
import whisper
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
        self._model = None
        self._current_model_name = None
    
    async def start(self):
        """启动工作器"""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        # 预加载默认模型
        await self._load_model(config.WHISPER_MODEL)
        
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
        
        # 清理模型
        self._model = None
        self._current_model_name = None
        logger.info("Whisper worker stopped")
    
    async def _load_model(self, model_name: str):
        """加载Whisper模型"""
        if self._current_model_name == model_name and self._model is not None:
            logger.info(f"Model {model_name} already loaded")
            return
        
        logger.info(f"Loading Whisper model: {model_name}")
        try:
            # 在线程池中加载模型，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None, 
                whisper.load_model, 
                model_name
            )
            self._current_model_name = model_name
            logger.info(f"Successfully loaded model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise
    
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
            
            # 如果需要不同的模型，重新加载
            await self._load_model(model)
            
            # 在线程池中进行转录，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._model.transcribe, 
                audio_path
            )
            
            # 将结果转换为SRT格式
            srt_content = self._result_to_srt(result)
            
            logger.info(f"Transcription completed, SRT length: {len(srt_content)} characters")
            return srt_content
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def _result_to_srt(self, result: dict) -> str:
        """将whisper结果转换为SRT格式"""
        srt_lines = []
        
        # 如果结果中包含segments，使用segments
        if 'segments' in result:
            for i, segment in enumerate(result['segments']):
                start_time = self._format_time(segment['start'])
                end_time = self._format_time(segment['end'])
                text = segment['text'].strip()
                
                srt_lines.append(f"{i + 1}")
                srt_lines.append(f"{start_time} --> {end_time}")
                srt_lines.append(text)
                srt_lines.append("")  # 空行分隔
        else:
            # 如果没有segments，创建一个简单的SRT
            srt_lines.append("1")
            srt_lines.append("00:00:00,000 --> 00:00:10,000")
            srt_lines.append(result.get('text', '').strip())
            srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    def _format_time(self, seconds: float) -> str:
        """将秒数格式化为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查工作器是否运行
            if not self.is_running:
                return False
            
            # 检查模型是否已加载
            if self._model is None:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取工作器状态"""
        return {
            "is_running": self.is_running,
            "model_loaded": self._model is not None,
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