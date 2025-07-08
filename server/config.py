import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # 任务池配置
    MAX_TASK_POOL_SIZE = int(os.getenv("MAX_TASK_POOL_SIZE", "5"))
    
    # 文件存储配置
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    RESULT_DIR = os.getenv("RESULT_DIR", "results")
    TEMP_DIR = os.getenv("TEMP_DIR", "temp")
    
    # Whisper配置
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3-turbo")
    
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    # 安全配置（预留用于将来扩展）
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # 任务清理配置
    RESULT_RETENTION_HOURS = int(os.getenv("RESULT_RETENTION_HOURS", "24"))
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        for dir_path in [cls.UPLOAD_DIR, cls.RESULT_DIR, cls.TEMP_DIR]:
            os.makedirs(dir_path, exist_ok=True)

# 全局配置实例
config = Config() 