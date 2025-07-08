#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRT文件清理工具
用于处理Whisper识别产生的崩坏重复内容
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import Counter
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('srt_cleaner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SRTEntry:
    """SRT字幕条目"""
    def __init__(self, index: int, start_time: str, end_time: str, text: str):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.text = text.strip()
    
    def __str__(self):
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}\n"
    
    def __repr__(self):
        return f"SRTEntry(index={self.index}, text='{self.text[:30]}...')"


class SRTCleaner:
    """SRT文件清理器"""
    
    def __init__(self, repeat_threshold: int = 3):
        """
        初始化SRT清理器
        
        Args:
            repeat_threshold: 连续重复条数阈值，默认为3
        """
        self.repeat_threshold = repeat_threshold
        self.processed_files = 0
        self.total_removed = 0
        self.global_duplicates = Counter()
    
    def parse_srt_file(self, file_path: str) -> List[SRTEntry]:
        """
        解析SRT文件
        
        Args:
            file_path: SRT文件路径
            
        Returns:
            SRT条目列表
        """
        entries = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gb2312') as f:
                    content = f.read()
            except UnicodeDecodeError:
                logger.error(f"无法读取文件 {file_path}，编码问题")
                return []
        
        # 使用正则表达式解析SRT格式
        srt_pattern = re.compile(
            r'(\d+)\s*\n'  # 序号
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'  # 时间戳
            r'(.*?)\n(?=\n|\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}|$)',  # 文本内容
            re.DOTALL
        )
        
        matches = srt_pattern.findall(content)
        
        for match in matches:
            index = int(match[0])
            start_time = match[1]
            end_time = match[2]
            text = match[3].strip()
            
            if text:  # 只添加非空文本
                entries.append(SRTEntry(index, start_time, end_time, text))
        
        return entries
    
    def normalize_text(self, text: str) -> str:
        """
        标准化文本，用于比较
        
        Args:
            text: 原始文本
            
        Returns:
            标准化后的文本
        """
        # 去除多余的空格和标点符号
        text = re.sub(r'\s+', ' ', text.strip())
        # 转换为小写用于比较
        return text.lower()
    
    def find_consecutive_duplicates(self, entries: List[SRTEntry]) -> List[Tuple[int, int, str]]:
        """
        查找连续重复的字幕条目
        
        Args:
            entries: SRT条目列表
            
        Returns:
            重复范围列表 [(start_index, end_index, text), ...]
        """
        if len(entries) < self.repeat_threshold:
            return []
        
        duplicate_ranges = []
        i = 0
        
        while i < len(entries):
            current_text = self.normalize_text(entries[i].text)
            count = 1
            j = i + 1
            
            # 统计连续相同的条目
            while j < len(entries) and self.normalize_text(entries[j].text) == current_text:
                count += 1
                j += 1
            
            # 如果连续重复数量达到阈值，记录这个范围
            if count >= self.repeat_threshold:
                duplicate_ranges.append((i, j - 1, current_text))
                logger.info(f"发现重复范围: 第{i+1}-{j}条, 重复{count}次: '{entries[i].text[:50]}...'")
            
            i = j if count >= self.repeat_threshold else i + 1
        
        return duplicate_ranges
    
    def remove_duplicates(self, entries: List[SRTEntry]) -> List[SRTEntry]:
        """
        移除重复的字幕条目，保留第一条
        
        Args:
            entries: 原始SRT条目列表
            
        Returns:
            清理后的SRT条目列表
        """
        if not entries:
            return entries
        
        duplicate_ranges = self.find_consecutive_duplicates(entries)
        
        if not duplicate_ranges:
            logger.info("未发现连续重复的字幕内容")
            return entries
        
        # 创建要移除的索引集合
        indices_to_remove = set()
        
        for start_idx, end_idx, text in duplicate_ranges:
            # 保留第一条，移除其余的
            for idx in range(start_idx + 1, end_idx + 1):
                indices_to_remove.add(idx)
            
            removed_count = end_idx - start_idx
            self.total_removed += removed_count
            logger.info(f"移除了 {removed_count} 条重复字幕: '{text[:50]}...'")
        
        # 过滤掉要移除的条目
        cleaned_entries = [entry for i, entry in enumerate(entries) if i not in indices_to_remove]
        
        # 重新编号
        for i, entry in enumerate(cleaned_entries):
            entry.index = i + 1
        
        return cleaned_entries
    
    def analyze_duplicates(self, entries: List[SRTEntry]) -> Dict[str, int]:
        """
        分析字幕中的重复词条
        
        Args:
            entries: SRT条目列表
            
        Returns:
            重复词条统计
        """
        text_counter = Counter()
        
        for entry in entries:
            normalized_text = self.normalize_text(entry.text)
            text_counter[normalized_text] += 1
            # 同时更新全局重复统计
            self.global_duplicates[normalized_text] += 1
        
        # 只返回出现次数大于1的词条
        duplicates = {text: count for text, count in text_counter.items() if count > 1}
        return duplicates
    
    def write_srt_file(self, entries: List[SRTEntry], output_path: str):
        """
        写入SRT文件
        
        Args:
            entries: SRT条目列表
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for entry in entries:
                    f.write(str(entry) + '\n')
            logger.info(f"已写入清理后的文件: {output_path}")
        except Exception as e:
            logger.error(f"写入文件失败 {output_path}: {e}")
    
    def process_file(self, input_path: str, output_path: str = None) -> bool:
        """
        处理单个SRT文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径，如果为None则覆盖原文件
            
        Returns:
            是否处理成功
        """
        logger.info(f"开始处理文件: {input_path}")
        
        if output_path is None:
            output_path = input_path
        
        # 解析SRT文件
        entries = self.parse_srt_file(input_path)
        if not entries:
            logger.warning(f"文件 {input_path} 没有有效的字幕内容")
            return False
        
        logger.info(f"原文件包含 {len(entries)} 条字幕")
        
        # 分析重复词条
        duplicates = self.analyze_duplicates(entries)
        if duplicates:
            logger.info(f"发现 {len(duplicates)} 个重复词条:")
            for text, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]:
                logger.info(f"  重复 {count} 次: '{text[:50]}...'")
        
        # 移除重复条目
        cleaned_entries = self.remove_duplicates(entries)
        
        logger.info(f"清理后包含 {len(cleaned_entries)} 条字幕")
        
        # 写入清理后的文件
        if cleaned_entries != entries:
            self.write_srt_file(cleaned_entries, output_path)
        else:
            logger.info("文件无需清理")
        
        self.processed_files += 1
        return True
    
    def process_directory(self, directory_path: str, output_directory: str = None):
        """
        处理目录中的所有SRT文件
        
        Args:
            directory_path: 输入目录路径
            output_directory: 输出目录路径，如果为None则覆盖原文件
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            logger.error(f"目录不存在: {directory_path}")
            return
        
        # 查找所有SRT文件
        srt_files = list(directory_path.glob('*.srt'))
        
        if not srt_files:
            logger.warning(f"目录 {directory_path} 中没有找到SRT文件")
            return
        
        logger.info(f"找到 {len(srt_files)} 个SRT文件")
        
        # 如果指定了输出目录，确保它存在
        if output_directory:
            output_directory = Path(output_directory)
            output_directory.mkdir(exist_ok=True)
        
        # 处理每个文件
        for srt_file in srt_files:
            if output_directory:
                output_path = output_directory / srt_file.name
            else:
                output_path = None
            
            try:
                self.process_file(str(srt_file), str(output_path) if output_path else None)
            except Exception as e:
                logger.error(f"处理文件 {srt_file} 时发生错误: {e}")
        
        # 输出全局统计信息
        self.print_global_statistics()
    
    def print_global_statistics(self):
        """打印全局统计信息"""
        logger.info("="*50)
        logger.info("全局统计信息:")
        logger.info(f"  处理的文件数: {self.processed_files}")
        logger.info(f"  总共移除的重复字幕: {self.total_removed}")
        
        # 显示最常见的重复词条
        if self.global_duplicates:
            logger.info(f"  发现 {len(self.global_duplicates)} 个不同的重复词条")
            logger.info("  最常见的重复词条:")
            for text, count in self.global_duplicates.most_common(10):
                if count > 1:
                    logger.info(f"    出现 {count} 次: '{text[:50]}...'")
        
        logger.info("="*50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SRT文件清理工具 - 移除Whisper识别产生的崩坏重复内容')
    parser.add_argument('input_path', help='输入SRT文件或目录路径')
    parser.add_argument('-o', '--output', help='输出文件或目录路径（可选，默认覆盖原文件）')
    parser.add_argument('-t', '--threshold', type=int, default=3, 
                       help='连续重复条数阈值（默认为3）')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # 创建清理器
    cleaner = SRTCleaner(repeat_threshold=args.threshold)
    
    input_path = Path(args.input_path)
    
    if input_path.is_file():
        # 处理单个文件
        cleaner.process_file(str(input_path), args.output)
    elif input_path.is_dir():
        # 处理目录
        cleaner.process_directory(str(input_path), args.output)
    else:
        logger.error(f"输入路径不存在: {input_path}")
        return
    
    logger.info("处理完成!")


if __name__ == '__main__':
    main() 