#!/usr/bin/env python3
"""
Whisper客户端运行脚本
提供简单的配置和启动方式
"""

import os
import sys
from pathlib import Path
from whisper_client import WhisperClient

def main():
    """主函数"""
    print("=" * 60)
    print("Whisper转录客户端")
    print("=" * 60)
    
    # 获取配置
    print("\n📁 请配置以下参数:")
    
    # 服务器地址
    server_url = input("服务器地址 (默认: http://localhost:8000): ").strip()
    if not server_url:
        server_url = "http://localhost:8000"
    
    # 扫描目录
    while True:
        scan_dir = input("视频文件目录 (必填): ").strip()
        if scan_dir and Path(scan_dir).exists():
            break
        print("❌ 目录不存在，请重新输入")
    
    # Whisper模型
    print("\n可用模型: tiny, base, small, medium, large-v1, large-v2, large-v3-turbo")
    model = input("Whisper模型 (默认: large-v3-turbo): ").strip()
    if not model:
        model = "large-v3-turbo"
    
    # 并发数
    max_workers_input = input("最大并发任务数 (默认: 2): ").strip()
    try:
        max_workers = int(max_workers_input) if max_workers_input else 2
        if max_workers < 1:
            max_workers = 1
        elif max_workers > 5:
            max_workers = 5
    except ValueError:
        max_workers = 2
    
    # 是否保留音频
    keep_audio_input = input("是否保留转换的音频文件? (y/N): ").strip().lower()
    keep_audio = keep_audio_input in ['y', 'yes', '是']
    
    print(f"\n🚀 开始处理...")
    print(f"服务器: {server_url}")
    print(f"目录: {scan_dir}")
    print(f"模型: {model}")
    print(f"并发数: {max_workers}")
    print(f"保留音频: {'是' if keep_audio else '否'}")
    print("-" * 60)
    
    try:
        # 创建客户端
        client = WhisperClient(
            server_url=server_url,
            scan_dir=scan_dir
        )
        
        # 检查服务器
        if not client.check_server_health():
            print("❌ 无法连接到服务器")
            return
        
        # 处理所有文件
        results = client.process_all_videos(
            model=model,
            max_workers=max_workers,
            keep_audio=keep_audio
        )
        
        if not results:
            print("没有找到需要处理的文件")
        else:
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            print("\n" + "=" * 60)
            print(f"🎉 处理完成: {success_count}/{total_count} 个文件成功")
            
            if success_count < total_count:
                print("❌ 部分文件处理失败，请查看日志")
            else:
                print("✅ 所有文件处理成功!")
            print("=" * 60)
    
    except KeyboardInterrupt:
        print("\n用户中断处理")
    except Exception as e:
        print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    main() 