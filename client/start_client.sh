#!/bin/bash

# Whisper转录客户端启动脚本

# 进入客户端目录
cd "$(dirname "$0")"

# 激活Python环境
source ~/Documents/envs/ai/bin/activate

# 检查ffmpeg是否安装
if ! command -v ffmpeg &> /dev/null; then
    echo "错误: ffmpeg未安装或未在PATH中"
    echo "请先安装ffmpeg:"
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
    echo "  CentOS: sudo yum install ffmpeg"
    exit 1
fi

# 检查Python依赖
echo "检查Python依赖..."
python -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: Python依赖不完整"
    echo "请先安装依赖: pip install -r requirements.txt"
    exit 1
fi

# 显示使用说明
echo "Whisper转录客户端"
echo "=================="
echo ""
echo "使用方法:"
echo "1. 交互式运行: python run_client.py"
echo "2. 命令行运行: python whisper_client.py --scan-dir /path/to/videos"
echo ""
echo "示例:"
echo "  python whisper_client.py --scan-dir ~/Videos --model large-v3-turbo"
echo "  python whisper_client.py --single ~/Videos/video.mp4"
echo ""

# 询问运行方式
echo "请选择运行方式:"
echo "1) 交互式配置运行"
echo "2) 命令行参数运行"
echo "3) 查看帮助"
read -p "请输入选择 [1-3]: " choice

case $choice in
    1)
        echo "启动交互式客户端..."
        python run_client.py
        ;;
    2)
        echo "使用命令行参数运行:"
        echo "python whisper_client.py \$@"
        python whisper_client.py "$@"
        ;;
    3)
        echo "显示详细帮助:"
        python whisper_client.py --help
        ;;
    *)
        echo "无效选择，退出"
        exit 1
        ;;
esac 