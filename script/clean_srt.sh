#!/bin/bash
# SRT文件清理工具启动脚本

# 获取脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 激活Python环境
source ~/Documents/envs/ai/bin/activate

# 进入脚本目录
cd "$SCRIPT_DIR"

echo "SRT文件清理工具"
echo "=================="
echo "目录: $SCRIPT_DIR"
echo ""

# 检查是否有参数
if [ $# -eq 0 ]; then
    echo "使用默认模式：处理当前目录下的所有SRT文件"
    python run_cleaner.py
else
    echo "使用自定义参数：$@"
    python srt_cleaner.py "$@"
fi

echo ""
echo "处理完成！" 