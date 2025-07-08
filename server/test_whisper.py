#!/usr/bin/env python3
"""
测试Whisper命令执行
"""
import os
import sys
import subprocess
import tempfile
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_whisper_command():
    """测试Whisper命令"""
    print("Testing Whisper command...")
    
    # 检查Whisper是否安装
    try:
        result = subprocess.run(['whisper', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"❌ Whisper command failed: {result.stderr}")
            return False
        print("✓ Whisper command is available")
    except Exception as e:
        print(f"❌ Whisper command not found: {e}")
        return False
    
    # 测试音频文件处理
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if not os.path.exists(audio_file):
            print(f"❌ Audio file not found: {audio_file}")
            return False
        
        print(f"Testing with audio file: {audio_file}")
        
        # 检查文件大小
        file_size = os.path.getsize(audio_file)
        print(f"Audio file size: {file_size} bytes")
        
        if file_size == 0:
            print("❌ Audio file is empty")
            return False
        
        # 创建临时输出目录
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Output directory: {temp_dir}")
            
            # 构建Whisper命令
            cmd = [
                'whisper', 
                audio_file,
                '--model', 'large-v3',
                '--output_dir', temp_dir,
                '--output_format', 'srt',
                '--language', 'auto',
                '--verbose', 'True'
            ]
            
            print(f"Command: {' '.join(cmd)}")
            
            # 执行命令
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                print(f"Return code: {result.returncode}")
                if result.stdout:
                    print(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    print(f"STDERR:\n{result.stderr}")
                
                # 检查输出文件
                output_files = os.listdir(temp_dir)
                print(f"Output files: {output_files}")
                
                # 查找SRT文件
                srt_files = [f for f in output_files if f.endswith('.srt')]
                if srt_files:
                    print(f"✓ Found SRT files: {srt_files}")
                    
                    # 读取SRT内容
                    srt_path = os.path.join(temp_dir, srt_files[0])
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"SRT content length: {len(content)} characters")
                    if len(content) > 0:
                        print(f"SRT content preview:\n{content[:500]}...")
                    
                    return True
                else:
                    print("❌ No SRT files generated")
                    return False
                    
            except subprocess.TimeoutExpired:
                print("❌ Command timeout")
                return False
            except Exception as e:
                print(f"❌ Command execution failed: {e}")
                return False
    
    else:
        print("No audio file provided for testing")
        return True

if __name__ == "__main__":
    success = test_whisper_command()
    sys.exit(0 if success else 1) 