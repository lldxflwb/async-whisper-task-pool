#!/usr/bin/env python3
"""
测试客户端上传流程
"""
import os
import sys
import tempfile
import json
import zipfile
import shutil
from pathlib import Path
from whisper_client import WhisperClient, FileEncryptor

def create_test_audio():
    """创建一个测试音频文件"""
    # 创建一个简单的测试音频文件（空文件用于测试）
    test_audio = Path("test_audio.ogg")
    test_audio.write_bytes(b"test audio content")  # 模拟音频数据
    return test_audio

def test_task_zip_creation():
    """测试任务包创建"""
    print("Testing task zip creation...")
    
    # 创建测试音频文件
    audio_path = create_test_audio()
    
    try:
        # 创建客户端实例
        client = WhisperClient(
            server_url="http://localhost:6006",
            scan_dir=".",
            output_dir="."
        )
        
        # 测试创建任务包
        task_id = "test-task-123"
        model = "large-v3"
        
        zip_path = client.create_task_zip(audio_path, task_id, model)
        
        if zip_path and zip_path.exists():
            print(f"✓ 任务包创建成功: {zip_path}")
            
            # 验证文件大小
            file_size = zip_path.stat().st_size
            print(f"文件大小: {file_size} bytes")
            
            if file_size > 0:
                print("✓ 文件不为空")
            else:
                print("❌ 文件为空")
                
            # 清理测试文件
            zip_path.unlink()
            
        else:
            print("❌ 任务包创建失败")
            
    finally:
        # 清理测试音频文件
        if audio_path.exists():
            audio_path.unlink()

def test_server_connection():
    """测试服务器连接"""
    print("Testing server connection...")
    
    client = WhisperClient(
        server_url="http://localhost:6006",
        scan_dir=".",
        output_dir="."
    )
    
    if client.check_server_health():
        print("✓ 服务器连接正常")
    else:
        print("❌ 服务器连接失败")

def main():
    """主函数"""
    print("客户端测试开始...")
    
    # 测试服务器连接
    test_server_connection()
    
    # 测试任务包创建
    test_task_zip_creation()
    
    print("客户端测试完成")

if __name__ == "__main__":
    main() 