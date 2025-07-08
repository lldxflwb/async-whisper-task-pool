import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from threading import Lock
from models import Task, TaskResult, TaskStatus, TaskMetadata, PoolStatusResponse
from config import config
from utils import FileManager
import os

logger = logging.getLogger(__name__)

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self._task_pool: Dict[str, Task] = {}
        self._result_pool: Dict[str, TaskResult] = {}
        self._processing_tasks: Dict[str, Task] = {}
        self._lock = Lock()
        self._max_pool_size = config.MAX_TASK_POOL_SIZE
        
        # 确保目录存在
        FileManager.ensure_directories()
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_expired_results())
    
    def is_pool_full(self) -> bool:
        """检查任务池是否满"""
        with self._lock:
            return len(self._task_pool) >= self._max_pool_size
    
    def get_pool_status(self) -> PoolStatusResponse:
        """获取任务池状态"""
        with self._lock:
            return PoolStatusResponse(
                is_full=len(self._task_pool) >= self._max_pool_size,
                current_size=len(self._task_pool),
                max_size=self._max_pool_size,
                processing_count=len(self._processing_tasks)
            )
    
    def add_task(self, task: Task) -> bool:
        """添加任务到任务池"""
        with self._lock:
            if len(self._task_pool) >= self._max_pool_size:
                return False
            
            # 如果任务已存在，覆盖它
            if task.id in self._task_pool:
                old_task = self._task_pool[task.id]
                # 清理旧任务的文件
                if old_task.zip_file_path:
                    FileManager.cleanup_task_files(old_task.id, old_task.zip_file_path)
                logger.info(f"Overwriting existing task: {task.id}")
            
            self._task_pool[task.id] = task
            logger.info(f"Added task to pool: {task.id}")
            return True
    
    def get_next_task(self) -> Optional[Task]:
        """获取下一个待处理的任务"""
        with self._lock:
            for task_id, task in self._task_pool.items():
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()
                    self._processing_tasks[task_id] = task
                    return task
            return None
    
    def complete_task(self, task_id: str, srt_content: str) -> bool:
        """完成任务"""
        with self._lock:
            if task_id not in self._task_pool:
                return False
            
            task = self._task_pool[task_id]
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # 保存结果
            try:
                result_path = FileManager.save_result(task_id, srt_content)
                result = TaskResult(
                    task_id=task_id,
                    srt_content=srt_content,
                    file_path=result_path
                )
                self._result_pool[task_id] = result
                
                # 只清理ZIP文件，保留结果文件
                if task.zip_file_path and os.path.exists(task.zip_file_path):
                    os.remove(task.zip_file_path)
                    logger.info(f"Cleaned up zip file: {task.zip_file_path}")
                
                # 从处理中任务池移除
                if task_id in self._processing_tasks:
                    del self._processing_tasks[task_id]
                
                # 从任务池移除
                del self._task_pool[task_id]
                
                logger.info(f"Task completed: {task_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to complete task {task_id}: {e}")
                self.fail_task(task_id, str(e))
                return False
    
    def fail_task(self, task_id: str, error_message: str) -> bool:
        """标记任务失败"""
        with self._lock:
            if task_id not in self._task_pool:
                return False
            
            task = self._task_pool[task_id]
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error_message = error_message
            
            # 清理任务文件
            FileManager.cleanup_task_files(task_id, task.zip_file_path)
            
            # 从处理中任务池移除
            if task_id in self._processing_tasks:
                del self._processing_tasks[task_id]
            
            logger.error(f"Task failed: {task_id}, Error: {error_message}")
            return True
    
    def get_task_status(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        with self._lock:
            return self._task_pool.get(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        with self._lock:
            return self._result_pool.get(task_id)
    
    def clear_task_result(self, task_id: str) -> bool:
        """清除任务结果"""
        with self._lock:
            if task_id in self._result_pool:
                result = self._result_pool[task_id]
                # 清理结果文件
                FileManager.cleanup_task_files(task_id)
                del self._result_pool[task_id]
                logger.info(f"Cleared task result: {task_id}")
                return True
            return False
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        with self._lock:
            return list(self._task_pool.values())
    
    def get_all_results(self) -> List[TaskResult]:
        """获取所有结果"""
        with self._lock:
            return list(self._result_pool.values())
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id in self._task_pool:
                task = self._task_pool[task_id]
                if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                    
                    # 清理任务文件
                    FileManager.cleanup_task_files(task_id, task.zip_file_path)
                    
                    # 从处理中任务池移除
                    if task_id in self._processing_tasks:
                        del self._processing_tasks[task_id]
                    
                    logger.info(f"Task cancelled: {task_id}")
                    return True
            return False
    
    async def _cleanup_expired_results(self):
        """清理过期的结果"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次
                
                with self._lock:
                    current_time = datetime.now()
                    expired_results = []
                    
                    for task_id, result in self._result_pool.items():
                        if current_time - result.created_at > timedelta(hours=config.RESULT_RETENTION_HOURS):
                            expired_results.append(task_id)
                    
                    for task_id in expired_results:
                        self.clear_task_result(task_id)
                        logger.info(f"Expired result cleaned: {task_id}")
                        
            except Exception as e:
                logger.error(f"Error in cleanup expired results: {e}")
    
    def get_task_count_by_status(self) -> Dict[TaskStatus, int]:
        """按状态统计任务数量"""
        with self._lock:
            counts = {status: 0 for status in TaskStatus}
            for task in self._task_pool.values():
                counts[task.status] += 1
            return counts
    
    def cleanup_all(self):
        """清理所有任务和结果"""
        with self._lock:
            # 清理所有任务文件
            for task in self._task_pool.values():
                FileManager.cleanup_task_files(task.id, task.zip_file_path)
            
            # 清理所有结果文件
            for result in self._result_pool.values():
                FileManager.cleanup_task_files(result.task_id)
            
            # 清空池
            self._task_pool.clear()
            self._result_pool.clear()
            self._processing_tasks.clear()
            
            logger.info("All tasks and results cleaned up")

# 全局任务管理器实例
task_manager = TaskManager() 