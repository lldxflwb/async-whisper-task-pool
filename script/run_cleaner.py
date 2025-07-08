#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRT清理工具使用示例
"""

import os
import sys
import argparse
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from srt_cleaner import SRTCleaner

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SRT文件清理工具 - 简单版本')
    parser.add_argument('directory', nargs='?', default='.', 
                       help='要处理的目录路径（默认为当前目录）')
    parser.add_argument('-t', '--threshold', type=int, default=3,
                       help='连续重复条数阈值（默认为3）')
    parser.add_argument('-o', '--output', 
                       help='输出目录路径（可选，默认覆盖原文件）')
    
    args = parser.parse_args()
    
    # 处理目录路径
    input_directory = Path(args.directory).resolve()
    
    if not input_directory.exists():
        print(f"错误：目录不存在: {input_directory}")
        return
    
    if not input_directory.is_dir():
        print(f"错误：路径不是目录: {input_directory}")
        return
    
    # 创建清理器
    cleaner = SRTCleaner(repeat_threshold=args.threshold)
    
    print("开始处理SRT文件...")
    print(f"处理目录: {input_directory}")
    print(f"重复阈值: {cleaner.repeat_threshold}")
    if args.output:
        print(f"输出目录: {args.output}")
    print("-" * 50)
    
    # 处理目录
    cleaner.process_directory(str(input_directory), args.output)
    
    print("处理完成!")

if __name__ == '__main__':
    main() 