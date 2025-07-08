# SRT文件清理工具使用说明

## 概述

这个工具用于清理Whisper识别产生的崩坏重复内容。当Whisper识别出现问题时，经常会产生连续重复的字幕内容，这个工具可以自动检测并移除这些重复内容。

## 文件说明

- `srt_cleaner.py` - 主要的清理工具（完整版）
- `run_cleaner.py` - 简化版本，支持指定目录
- `clean_srt.sh` - Shell启动脚本
- `USAGE.md` - 本使用说明文档

## 快速开始

### 方法1：使用简化版本

```bash
# 处理指定目录
python run_cleaner.py /path/to/srt/directory

# 处理当前目录
python run_cleaner.py

# 指定重复阈值和输出目录
python run_cleaner.py /path/to/srt/directory -t 5 -o /path/to/output
```

### 方法2：使用Shell脚本

```bash
# 快速处理（默认当前目录）
./clean_srt.sh

# 或者传递参数
./clean_srt.sh /path/to/srt/directory -t 5
```

### 方法3：使用完整版本

```bash
# 处理单个文件
python srt_cleaner.py input.srt

# 处理整个目录
python srt_cleaner.py /path/to/srt/directory

# 指定输出目录
python srt_cleaner.py /path/to/srt/directory -o /path/to/output

# 自定义重复阈值
python srt_cleaner.py /path/to/srt/directory -t 5

# 详细输出
python srt_cleaner.py /path/to/srt/directory -v
```

## 参数说明

### 简化版本 (run_cleaner.py)
- `directory` - 要处理的目录路径（可选，默认为当前目录）
- `-t, --threshold` - 连续重复条数阈值（默认为3）
- `-o, --output` - 输出目录路径（可选，默认覆盖原文件）

### 完整版本 (srt_cleaner.py)
- `input_path` - 输入SRT文件或目录路径（必需）
- `-o, --output` - 输出文件或目录路径（可选，默认覆盖原文件）
- `-t, --threshold` - 连续重复条数阈值（默认为3）
- `-v, --verbose` - 详细输出

## 工作原理

1. **解析SRT文件**：支持UTF-8和GB2312编码
2. **文本标准化**：去除多余空格，转换为小写用于比较
3. **检测重复**：查找连续重复的字幕内容
4. **移除重复**：保留第一条，移除其余重复的字幕
5. **重新编号**：为清理后的字幕重新编号
6. **生成报告**：显示处理统计信息

## 使用示例

### 处理指定目录

```bash
# 处理指定目录的所有SRT文件
python run_cleaner.py /path/to/video/subtitles

# 输出结果：
# 开始处理SRT文件...
# 处理目录: /path/to/video/subtitles
# 重复阈值: 3
# --------------------------------------------------
# 2025-07-08 16:25:45,169 - INFO - 找到 2 个SRT文件
# 2025-07-08 16:25:45,170 - INFO - 开始处理文件: test_repeats.srt
# 2025-07-08 16:25:45,170 - INFO - 原文件包含 13 条字幕
# 2025-07-08 16:25:45,170 - INFO - 发现 2 个重复词条:
# 2025-07-08 16:25:45,170 - INFO -   重复 5 次: 'this is repeated content....'
# 2025-07-08 16:25:45,170 - INFO -   重复 3 次: 'broken audio loop....'
# 2025-07-08 16:25:45,170 - INFO - 发现重复范围: 第4-8条, 重复5次
# 2025-07-08 16:25:45,170 - INFO - 发现重复范围: 第11-13条, 重复3次
# 2025-07-08 16:25:45,171 - INFO - 移除了 4 条重复字幕
# 2025-07-08 16:25:45,171 - INFO - 移除了 2 条重复字幕
# 2025-07-08 16:25:45,171 - INFO - 清理后包含 7 条字幕
# 处理完成!
```

### 指定输出目录

```bash
# 处理文件并输出到指定目录
python run_cleaner.py /input/srt/directory -o /output/cleaned/directory
```

### 自定义阈值

```bash
# 使用更严格的阈值（连续2条重复就清理）
python run_cleaner.py /path/to/srt/directory -t 2

# 使用更宽松的阈值（连续5条重复才清理）
python run_cleaner.py /path/to/srt/directory -t 5
```

## 配置选项

### 重复阈值

默认情况下，工具会检测连续3条或更多的重复内容。你可以通过`-t`参数调整：

```bash
# 检测连续5条或更多的重复
python run_cleaner.py /path/to/srt/directory -t 5

# 检测连续2条或更多的重复（更敏感）
python run_cleaner.py /path/to/srt/directory -t 2
```

### 输出选项

```bash
# 覆盖原文件（默认）
python run_cleaner.py /path/to/srt/directory

# 输出到新目录
python run_cleaner.py /path/to/srt/directory -o /output/directory
```

## 注意事项

1. **备份原文件**：工具默认会覆盖原文件，建议先备份
2. **编码支持**：支持UTF-8和GB2312编码
3. **日志记录**：处理过程会记录到`srt_cleaner.log`文件
4. **错误处理**：遇到无法处理的文件会跳过并记录错误
5. **目录验证**：会自动检查目录是否存在和有效

## 适用场景

- Whisper识别产生的重复字幕
- 其他ASR工具产生的重复内容
- 需要批量处理多个SRT文件的场景
- 处理指定目录下的所有SRT文件

## 技术细节

- 使用正则表达式解析SRT格式
- 文本标准化确保准确匹配
- 保持原有时间戳格式
- 自动重新编号字幕序号
- 支持相对路径和绝对路径 