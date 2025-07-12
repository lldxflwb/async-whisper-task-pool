# Whisper 转录 API

基于 Whisper 的异步音频转录服务，支持批量处理视频文件并生成字幕。

## 快速开始

### 服务端部署

1. **环境准备**
```bash
# 激活 Python 环境
source ~/Documents/envs/ai/bin/activate

# 安装依赖
cd server
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
# 复制并编辑配置文件
cp env.template .env
# 编辑 .env 文件设置相关参数
```

3. **启动服务**
```bash
./start_server.sh
# 或
python main.py
```

### 客户端使用

1. **安装依赖**
```bash
cd client
pip install -r requirements.txt
```

2. **批量处理视频**
```bash
python whisper_client.py --scan-dir /path/to/videos --server-url http://localhost:6006
```

## 功能特点

- ✅ **异步处理** - 基于 FastAPI 的高性能异步服务
- ✅ **批量转换** - 客户端支持批量扫描和处理视频文件
- ✅ **智能轮询** - 根据任务状态采用不同轮询策略
- ✅ **加密传输** - 任务文件使用加密压缩包传输
- ✅ **多格式支持** - 支持 MP4、AVI、MKV 等主流视频格式
- ✅ **后处理工具** - 包含 SRT 字幕清理工具

## 架构说明

### 组件结构
- **服务端** (`server/`) - FastAPI 异步 API 服务器
- **客户端** (`client/`) - Python 批量处理客户端  
- **后处理** (`script/`) - SRT 字幕清理工具

### 工作流程
1. 客户端扫描视频文件 → 转换为音频 → 打包上传
2. 服务端接收任务 → 队列管理 → Whisper 转录
3. 客户端轮询结果 → 下载字幕 → 清理临时文件

## 详细文档

- [使用指南](USAGE.md) - 详细的安装和使用说明
- [客户端文档](client/README.md) - 客户端功能和参数说明  
- [Whisper 安装](server/WHISPER_INSTALL.md) - Whisper 命令行工具安装
- [开发指南](CLAUDE.md) - 面向开发者的架构和命令说明

## 技术栈

- **后端**: FastAPI, uvicorn, asyncio
- **AI**: OpenAI Whisper (CLI)
- **音频处理**: FFmpeg  
- **加密**: cryptography (Fernet)
- **并发**: concurrent.futures, asyncio

## 支持的格式

**输入视频**: MP4, AVI, MKV, MOV, WMV, FLV, M4V, WEBM
**输出字幕**: SRT 格式

## 许可证

本项目为个人或内部使用项目。