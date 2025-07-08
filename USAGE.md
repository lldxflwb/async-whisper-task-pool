# Whisper转录API服务使用说明

## 项目概述

这是一个基于Whisper的异步音频转录API服务，专为auto-dl等平台设计。服务提供任务池管理、结果缓存、文件加密等功能。

## 项目结构

```
WhisperApi/
├── main.py              # 主服务器入口
├── api.py              # FastAPI接口定义
├── models.py           # 数据模型
├── config.py           # 配置管理
├── task_manager.py     # 任务池和结果池管理
├── whisper_worker.py   # Whisper转录工作器
├── utils.py            # 工具函数（文件处理、加密等）
├── requirements.txt    # Python依赖
├── start_server.sh     # 启动脚本
├── api_example.py      # API使用示例
├── .gitignore          # Git忽略文件
└── USAGE.md           # 使用说明
```

## 安装依赖

1. 激活Python环境：
```bash
source ~/Documents/envs/ai/bin/activate
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 启动服务

### 方式1：使用启动脚本
```bash
./start_server.sh
```

### 方式2：直接运行Python
```bash
python main.py
```

### 方式3：自定义参数
```bash
python main.py --host 0.0.0.0 --port 8000 --log-level info
```

## 环境变量配置

创建`.env`文件（可选）：
```bash
# 任务池配置
MAX_TASK_POOL_SIZE=5

# 文件存储配置
UPLOAD_DIR=uploads
RESULT_DIR=results
TEMP_DIR=temp

# Whisper配置
WHISPER_MODEL=large-v3-turbo

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 安全配置
SECRET_KEY=your-secret-key-here

# 任务清理配置（小时）
RESULT_RETENTION_HOURS=24
```

## API接口说明

### 健康检查
```bash
GET /health
```

### 任务池状态
```bash
GET /pool/status
```
返回：
```json
{
  "is_full": false,
  "current_size": 0,
  "max_size": 5,
  "processing_count": 0
}
```

### 提交任务
```bash
POST /tasks/submit
```
表单数据：
- `task_id`: 任务ID（UUID）
- `password`: 解压密码
- `model`: 使用的模型（默认：large-v3-turbo）
- `audio_file`: 音频文件（OGG格式）

### 获取任务状态
```bash
GET /tasks/{task_id}/status
```

### 获取任务结果
```bash
GET /tasks/{task_id}/result
```

### 下载结果文件
```bash
GET /tasks/{task_id}/result/download
```

### 清除任务结果
```bash
DELETE /tasks/{task_id}/result
```

### 取消任务
```bash
DELETE /tasks/{task_id}
```

## 使用示例

### 1. 基本使用流程

1. 检查服务器状态
2. 检查任务池是否满
3. 提交任务
4. 轮询任务状态/结果
5. 下载结果文件
6. 清除结果（可选）

### 2. 客户端示例

参考`api_example.py`文件，它展示了完整的客户端使用流程。

### 3. cURL示例

```bash
# 检查健康状态
curl http://localhost:8000/health

# 提交任务
curl -X POST http://localhost:8000/tasks/submit \
  -F "task_id=12345678-1234-1234-1234-123456789012" \
  -F "password=test123" \
  -F "model=large-v3-turbo" \
  -F "audio_file=@audio.ogg"

# 获取任务状态
curl http://localhost:8000/tasks/12345678-1234-1234-1234-123456789012/status

# 获取结果
curl http://localhost:8000/tasks/12345678-1234-1234-1234-123456789012/result

# 下载结果文件
curl http://localhost:8000/tasks/12345678-1234-1234-1234-123456789012/result/download -o result.srt
```

## 交互流程

1. **客户端**通过表单直接上传音频文件到服务器
2. **服务器**创建加密压缩包，将任务放入任务池，返回确认
3. **客户端**轮询获取任务结果
4. **服务器**单线程执行转录任务
5. **任务完成**后，结果放入结果池，清理任务文件

## 文件格式要求

- 音频文件必须是OGG格式
- 文件名必须是`audio.ogg`
- 压缩包包含metadata.json和audio.ogg
- 压缩包使用密码加密

## 注意事项

1. 任务池大小限制（默认5个）
2. 结果会在24小时后自动清理
3. 相同task_id的新任务会覆盖旧任务
4. 支持的Whisper模型：base, small, medium, large-v1, large-v2, large-v3-turbo
5. 服务器单线程处理任务，确保系统资源合理使用

## 故障排除

### 常见问题

1. **Whisper未安装**
   ```bash
   pip install openai-whisper
   ```

2. **端口被占用**
   ```bash
   python main.py --port 8001
   ```

3. **权限问题**
   ```bash
   chmod +x start_server.sh
   ```

4. **依赖问题**
   ```bash
   pip install -r requirements.txt
   ```

### 日志查看

服务器日志会输出到控制台和`whisper_api.log`文件。

## 开发和测试

### 开发模式启动
```bash
python main.py --reload
```

### 测试API
```bash
python api_example.py
```

确保有一个名为`example_audio.ogg`的测试音频文件。 