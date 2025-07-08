from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消

class TaskMetadata(BaseModel):
    """任务元数据"""
    task_id: str = Field(..., description="任务ID (UUID)")
    filename: str = Field(..., description="原始文件名")
    password: str = Field(..., description="解压密码")
    model: str = Field(default="large-v3-turbo", description="使用的模型")
    submit_time: datetime = Field(default_factory=datetime.now, description="提交时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Task(BaseModel):
    """任务信息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任务ID")
    metadata: TaskMetadata = Field(..., description="任务元数据")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    zip_file_path: Optional[str] = Field(None, description="压缩文件路径")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskResult(BaseModel):
    """任务结果"""
    task_id: str = Field(..., description="任务ID")
    srt_content: str = Field(..., description="SRT字幕内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    file_path: Optional[str] = Field(None, description="结果文件路径")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""
    task_id: str = Field(..., description="任务ID")
    password: str = Field(..., description="解压密码")
    model: str = Field(default="large-v3-turbo", description="使用的模型")

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskResultResponse(BaseModel):
    """任务结果响应"""
    task_id: str = Field(..., description="任务ID")
    srt_content: Optional[str] = Field(None, description="SRT字幕内容")
    status: TaskStatus = Field(..., description="任务状态")
    
class PoolStatusResponse(BaseModel):
    """任务池状态响应"""
    is_full: bool = Field(..., description="任务池是否满")
    current_size: int = Field(..., description="当前任务数量")
    max_size: int = Field(..., description="最大任务数量")
    processing_count: int = Field(..., description="正在处理的任务数量")

class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据") 