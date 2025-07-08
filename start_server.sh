#!/bin/bash

# Whisper转录API服务启动脚本

# 激活Python环境
source ~/Documents/envs/ai/bin/activate

# 检查Whisper是否安装
if ! command -v whisper &> /dev/null; then
    echo "错误: Whisper未安装或未在PATH中"
    echo "请先安装Whisper: pip install openai-whisper"
    exit 1
fi

# 检查Python依赖
echo "检查Python依赖..."
python -c "import fastapi, uvicorn, whisper, cryptography" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: Python依赖不完整"
    echo "请先安装依赖: pip install -r requirements.txt"
    exit 1
fi

# 启动服务器
echo "启动Whisper转录API服务..."
python main.py "$@" 