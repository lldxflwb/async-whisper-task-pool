from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import tempfile
from typing import Optional
from datetime import datetime

from models import (
    Task, TaskResult, TaskStatus, TaskMetadata, 
    TaskSubmissionRequest, TaskStatusResponse, 
    TaskResultResponse, PoolStatusResponse, ApiResponse
)
from task_manager import task_manager
from whisper_worker import worker, start_worker, stop_worker
from utils import ZipFileHandler, FileManager, setup_logging
from config import config

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper转录API",
    description="异步音频转录服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """应用启动时的事件"""
    logger.info("Starting Whisper API server...")
    
    # 确保目录存在
    FileManager.ensure_directories()
    
    # 启动Whisper工作器
    await start_worker()
    
    logger.info("Whisper API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的事件"""
    logger.info("Shutting down Whisper API server...")
    
    # 停止工作器
    await stop_worker()
    
    logger.info("Whisper API server shut down successfully")

@app.get("/", response_model=ApiResponse)
async def root():
    """根路径"""
    return ApiResponse(
        success=True,
        message="Whisper转录API服务正在运行",
        data={"version": "1.0.0", "status": "healthy"}
    )

@app.get("/health", response_model=dict)
async def health_check():
    """健康检查"""
    try:
        worker_health = await worker.health_check()
        pool_status = task_manager.get_pool_status()
        
        return {
            "status": "healthy" if worker_health else "unhealthy",
            "worker_running": worker.is_running,
            "pool_status": pool_status.dict(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

@app.get("/pool/status", response_model=PoolStatusResponse)
async def get_pool_status():
    """获取任务池状态"""
    try:
        return task_manager.get_pool_status()
    except Exception as e:
        logger.error(f"Get pool status failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pool status")

@app.post("/tasks/submit", response_model=ApiResponse)
async def submit_task(
    task_id: str = Form(...),
    task_file: UploadFile = File(...)
):
    """提交任务到任务池"""
    try:
        # 检查任务池是否满
        if task_manager.is_pool_full():
            raise HTTPException(status_code=429, detail="Task pool is full")
        
        # 验证任务文件
        if not task_file.filename.endswith('.zip.enc'):
            raise HTTPException(
                status_code=400, 
                detail="Task file must be encrypted zip format (.zip.enc)"
            )
        
        # 保存上传的任务文件
        zip_file_path = os.path.join(config.UPLOAD_DIR, f"{task_id}.zip.enc")
        
        try:
            with open(zip_file_path, 'wb') as f:
                content = await task_file.read()
                f.write(content)
            
            # 解压并验证任务文件，获取metadata
            try:
                extracted_data = ZipFileHandler.extract_task_zip(
                    zip_file_path, 
                    "whisper-task-password"  # 固定密码
                )
                metadata_dict = extracted_data['metadata']
                
                # 创建任务元数据对象
                metadata = TaskMetadata(
                    task_id=metadata_dict['task_id'],
                    filename=metadata_dict['filename'],
                    password=metadata_dict['password'],
                    model=metadata_dict['model']
                )
                
            except Exception as e:
                logger.error(f"Failed to extract task metadata: {e}")
                # 清理上传的文件
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid task file format or encryption"
                )
            
            # 创建任务
            task = Task(
                id=task_id,
                metadata=metadata,
                zip_file_path=zip_file_path
            )
            
            # 添加任务到任务池
            if task_manager.add_task(task):
                return ApiResponse(
                    success=True,
                    message="Task submitted successfully",
                    data={"task_id": task_id}
                )
            else:
                # 清理上传的文件
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                raise HTTPException(status_code=500, detail="Failed to add task to pool")
                
        except Exception as e:
            # 清理上传的文件
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)
            raise e
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit task failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

@app.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_message=task.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get task status failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task status")

@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str):
    """获取任务结果"""
    try:
        # 先检查任务状态
        task = task_manager.get_task_status(task_id)
        if task:
            # 任务仍在处理中
            return TaskResultResponse(
                task_id=task_id,
                srt_content=None,
                status=task.status
            )
        
        # 检查结果池
        result = task_manager.get_task_result(task_id)
        if result:
            return TaskResultResponse(
                task_id=task_id,
                srt_content=result.srt_content,
                status=TaskStatus.COMPLETED
            )
        
        # 任务和结果都不存在
        raise HTTPException(status_code=404, detail="Task not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get task result failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task result")

@app.get("/tasks/{task_id}/result/download", response_class=PlainTextResponse)
async def download_task_result(task_id: str):
    """下载任务结果SRT文件"""
    try:
        result = task_manager.get_task_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task result not found")
        
        return PlainTextResponse(
            content=result.srt_content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={task_id}.srt"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download task result failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to download task result")

@app.delete("/tasks/{task_id}/result", response_model=ApiResponse)
async def clear_task_result(task_id: str):
    """清除任务结果"""
    try:
        if task_manager.clear_task_result(task_id):
            return ApiResponse(
                success=True,
                message="Task result cleared successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Task result not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear task result failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear task result")

@app.delete("/tasks/{task_id}", response_model=ApiResponse)
async def cancel_task(task_id: str):
    """取消任务"""
    try:
        if task_manager.cancel_task(task_id):
            return ApiResponse(
                success=True,
                message="Task cancelled successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel task failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel task")

@app.get("/tasks", response_model=dict)
async def list_tasks():
    """列出所有任务"""
    try:
        tasks = task_manager.get_all_tasks()
        results = task_manager.get_all_results()
        
        return {
            "tasks": [
                {
                    "task_id": task.id,
                    "status": task.status,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message
                }
                for task in tasks
            ],
            "results": [
                {
                    "task_id": result.task_id,
                    "created_at": result.created_at.isoformat(),
                    "srt_length": len(result.srt_content)
                }
                for result in results
            ]
        }
    except Exception as e:
        logger.error(f"List tasks failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tasks")

@app.get("/stats", response_model=dict)
async def get_stats():
    """获取统计信息"""
    try:
        pool_status = task_manager.get_pool_status()
        task_counts = task_manager.get_task_count_by_status()
        worker_status = worker.get_status()
        
        return {
            "pool_status": pool_status.dict(),
            "task_counts": {status.value: count for status, count in task_counts.items()},
            "worker_status": worker_status,
            "result_count": len(task_manager.get_all_results())
        }
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")

# 错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    ) 