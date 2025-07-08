#!/usr/bin/env python3
"""
Whisper转录API服务主入口
"""

import uvicorn
import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import config
from utils import setup_logging

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Whisper转录API服务")
    parser.add_argument(
        "--host", 
        default=config.HOST,
        help=f"服务器主机地址 (默认: {config.HOST})"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=config.PORT,
        help=f"服务器端口 (默认: {config.PORT})"
    )
    parser.add_argument(
        "--reload", 
        action="store_true",
        help="启用热重载 (仅开发环境使用)"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=1,
        help="工作进程数量 (默认: 1)"
    )
    parser.add_argument(
        "--log-level", 
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="日志级别 (默认: info)"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 确保必要的目录存在
    config.ensure_directories()
    
    print(f"启动Whisper转录API服务...")
    print(f"主机地址: {args.host}")
    print(f"端口: {args.port}")
    print(f"任务池大小: {config.MAX_TASK_POOL_SIZE}")
    print(f"Whisper模型: {config.WHISPER_MODEL}")
    print(f"上传目录: {config.UPLOAD_DIR}")
    print(f"结果目录: {config.RESULT_DIR}")
    print(f"临时目录: {config.TEMP_DIR}")
    
    # 启动服务器
    uvicorn.run(
        "api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=args.log_level,
        access_log=True
    )

if __name__ == "__main__":
    main() 