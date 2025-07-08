# Whisper 转录 API 使用指南

## 概述

这是一个基于 Whisper 的异步音频转录服务，支持批量处理视频文件并生成字幕。

## 架构说明

### 交互流程

1. **客户端**：扫描视频文件 → 转换为音频 → 创建加密压缩包 → 上传到服务器
2. **服务端**：接收压缩包 → 解压获取音频 → 使用 Whisper 转录 → 返回 SRT 字幕
3. **客户端**：轮询获取结果 → 保存字幕文件 → 清理临时文件

### 文件格式

- **音频格式**：统一转换为 OGG 格式 (16kHz, 单声道, 24k比特率)
- **压缩包**：加密的 ZIP 文件，包含音频文件和任务元数据
- **字幕格式**：SRT 格式

## 服务端部署

### 1. 环境准备

```bash
# 激活 Python 环境
source ~/Documents/envs/ai/bin/activate

# 安装依赖
cd server
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# 任务池配置
MAX_TASK_POOL_SIZE=5

# 目录配置
UPLOAD_DIR=uploads
RESULT_DIR=results
TEMP_DIR=temp

# Whisper 配置
WHISPER_MODEL=large-v3

# 服务器配置
HOST=0.0.0.0
PORT=6006

# 结果保留时间（小时）
RESULT_RETENTION_HOURS=24
```

### 3. 启动服务

```bash
# 使用启动脚本
./start_server.sh

# 或直接运行
python main.py
```

## 客户端使用

### 1. 安装依赖

```bash
cd client
pip install -r requirements.txt
```

### 2. 配置客户端

编辑 `run_client.py` 或直接使用命令行：

```bash
python whisper_client.py \
    --server-url http://localhost:6006 \
    --scan-dir /path/to/video/directory \
    --model large-v3 \
    --max-workers 2
```

### 3. 批量处理

```bash
# 交互式运行
python run_client.py

# 命令行运行
python whisper_client.py \
    --server-url http://your-server:6006 \
    --scan-dir /path/to/videos \
    --model large-v3 \
    --max-workers 2 \
    --keep-files  # 保留临时文件
```

### 4. 单个文件处理

```bash
python whisper_client.py \
    --server-url http://localhost:6006 \
    --scan-dir /path/to/video/directory \
    --single /path/to/video.mp4 \
    --model large-v3
```

## API 接口

### 健康检查

```bash
GET /health
```

### 提交任务

```bash
POST /tasks/submit
Content-Type: multipart/form-data

Parameters:
- task_id: string (任务ID)
- task_file: file (加密的ZIP文件)
```

### 获取任务状态

```bash
GET /tasks/{task_id}/status
```

### 获取任务结果

```bash
GET /tasks/{task_id}/result
```

### 下载字幕文件

```bash
GET /tasks/{task_id}/result/download
```

## 支持的模型

- `tiny`, `tiny.en`
- `base`, `base.en`
- `small`, `small.en`
- `medium`, `medium.en`
- `large-v1`, `large-v2`, `large-v3`
- `large`

## 支持的视频格式

- MP4 (.mp4)
- AVI (.avi)
- MKV (.mkv)
- MOV (.mov)
- WMV (.wmv)
- FLV (.flv)
- M4V (.m4v)
- WEBM (.webm)

## 配置说明

### 服务端配置

- `MAX_TASK_POOL_SIZE`: 最大任务池大小（默认5）
- `WHISPER_MODEL`: 默认 Whisper 模型
- `RESULT_RETENTION_HOURS`: 结果保留时间（小时）

### 客户端配置

- `--max-workers`: 并发处理数量（默认2）
- `--keep-files`: 保留临时文件（调试用）
- `--model`: 指定 Whisper 模型

## 故障排除

### 1. 服务端问题

```bash
# 检查 Whisper 安装
whisper --help

# 检查服务器日志
tail -f whisper_api.log

# 测试 Whisper 命令
python test_whisper.py /path/to/audio.ogg
```

### 2. 客户端问题

```bash
# 检查 ffmpeg 安装
ffmpeg -version

# 检查服务器连接
curl http://localhost:6006/health

# 调试模式运行
python whisper_client.py --keep-files ...
```

### 3. 常见错误

- **"No SRT file generated"**: 检查音频文件是否为空或损坏
- **"Task pool is full"**: 等待任务完成或增加任务池大小
- **"ffmpeg not found"**: 安装 ffmpeg
- **"Connection refused"**: 检查服务器是否运行

## 性能优化

### 服务端优化

- 使用 SSD 存储
- 增加内存容量
- 根据 CPU 核心数调整任务池大小

### 客户端优化

- 调整 `--max-workers` 参数
- 使用本地网络减少延迟
- 批量处理相同目录的文件

## 安全说明

- 任务文件使用 PBKDF2 + Fernet 加密
- 密码固定为 `whisper-task-password`
- 结果文件自动清理
- 临时文件安全删除

## 日志和监控

- 服务端日志：`whisper_api.log`
- 客户端日志：控制台输出
- 任务状态：通过 API 查询
- 系统状态：`/health` 端点 