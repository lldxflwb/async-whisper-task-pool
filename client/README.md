# Whisper转录客户端

自动扫描视频文件，转换为音频并提交到Whisper API服务器进行转录，生成SRT字幕文件。

## 功能特点

✅ **自动扫描** - 递归扫描指定目录下的视频文件  
✅ **智能跳过** - 自动跳过已有字幕的视频文件  
✅ **格式转换** - 使用ffmpeg转换视频为OGG音频格式  
✅ **串行提交，后台等待** - 检查服务端空闲后提交，新线程等待结果  
✅ **智能轮询** - 处理中任务5秒轮询，队列中任务15秒轮询  
✅ **进度跟踪** - 实时显示处理进度和状态  
✅ **错误恢复** - 单个文件失败不影响其他文件处理  
✅ **日志记录** - 详细的处理日志便于问题排查  

## 系统要求

- Python 3.8+
- ffmpeg (用于音视频转换)
- 可访问的Whisper API服务器

## 安装

1. **安装Python依赖**：
```bash
pip install -r requirements.txt
```

2. **安装ffmpeg**：
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

## 使用方法

### 方式1: 交互式运行
```bash
./start_client.sh
# 选择 1) 交互式配置运行
```

### 方式2: 命令行运行
```bash
python whisper_client.py --scan-dir /path/to/videos
```

### 方式3: 简单启动
```bash
python run_client.py
```

## 命令行参数

```bash
python whisper_client.py [选项]

必需参数:
  --scan-dir DIR        要扫描的视频文件目录

可选参数:
  --server URL          Whisper API服务器地址 (默认: http://localhost:8000)
  --output-dir DIR      字幕文件输出目录 (默认: 与视频文件同目录)
  --model MODEL         Whisper模型 (默认: large-v3-turbo)
  --keep-audio          保留转换的音频文件
  --single FILE         只处理指定的单个视频文件
  --pending-poll-interval N     队列中任务的轮询间隔(秒) (默认: 15)
  --processing-poll-interval N  处理中任务的轮询间隔(秒) (默认: 5)
```

## 使用示例

### 基本使用
```bash
# 处理指定目录下的所有视频
python whisper_client.py --scan-dir ~/Videos

# 使用不同的模型
python whisper_client.py --scan-dir ~/Videos --model base

# 处理单个文件
python whisper_client.py --single ~/Videos/movie.mp4

# 保留转换的音频文件
python whisper_client.py --scan-dir ~/Videos --keep-audio
```

### 高级使用
```bash
# 使用远程服务器
python whisper_client.py \
  --server http://192.168.1.100:8000 \
  --scan-dir ~/Videos \
  --model large-v3-turbo

# 指定输出目录
python whisper_client.py \
  --scan-dir ~/Videos \
  --output-dir ~/Subtitles

# 自定义轮询间隔
python whisper_client.py \
  --scan-dir ~/Videos \
  --pending-poll-interval 30 \
  --processing-poll-interval 3
```

## 支持的视频格式

- `.mp4` - MP4视频
- `.avi` - AVI视频
- `.mkv` - Matroska视频
- `.mov` - QuickTime视频
- `.wmv` - Windows Media视频
- `.flv` - Flash视频
- `.webm` - WebM视频
- `.m4v` - iTunes视频

## 工作流程

1. **扫描目录** - 递归查找所有支持的视频文件
2. **检查字幕** - 跳过已有`.srt`文件的视频
3. **串行处理** - 主线程一个文件一个文件地处理：
   - 音频转换：使用ffmpeg转换为OGG格式
   - 检查空闲：查询服务端任务池状态
   - 等待空闲：如果任务池满则等待5秒后重试
   - 提交任务：上传音频到Whisper API服务器
4. **后台等待** - 每个提交的任务在新线程中等待结果
5. **保存字幕** - 将SRT文件保存到视频目录
6. **清理文件** - 删除临时音频文件（可选保留）
7. **等待完成** - 程序退出前等待所有线程完成

## 智能轮询策略

客户端根据任务状态采用不同的轮询频率：

- **队列中任务 (pending)**: 每15秒查询一次状态
- **处理中任务 (processing)**: 每5秒查询一次状态
- **已完成任务 (completed)**: 每2秒快速检查结果

这种策略可以：
- 减少服务器负载（队列中任务轮询频率较低）
- 提高响应速度（处理中任务轮询频率较高）
- 支持自定义轮询间隔以适应不同的网络环境

## FFmpeg转换参数

客户端使用以下FFmpeg参数转换音频：
```bash
ffmpeg -i input.mp4 -vn -acodec libopus -ar 16000 -ac 1 -b:a 24k output.ogg
```

参数说明：
- `-vn` - 不包含视频流
- `-acodec libopus` - 使用Opus编码器
- `-ar 16000` - 采样率16kHz
- `-ac 1` - 单声道
- `-b:a 24k` - 音频比特率24kbps

## 配置选项

### 处理策略
- 串行处理：主线程一个文件一个文件地转录、压缩
- 检查空闲：每次提交前检查服务端任务池状态
- 等待空闲：如果任务池满则等待5秒后重试
- 后台等待：提交成功后在新线程中等待结果
- 程序退出：等待所有线程完成后才退出

### 轮询间隔配置
- `--pending-poll-interval 15` - 队列中任务轮询间隔（秒）
- `--processing-poll-interval 5` - 处理中任务轮询间隔（秒）
- 网络慢时可增加间隔以减少请求频率
- 高性能网络可减少间隔以提高响应速度

### 模型选择
- `tiny` - 最快，精度最低
- `base` - 较快，精度一般
- `small` - 平衡速度和精度
- `medium` - 较慢，精度较高
- `large-v1` - 慢，精度高
- `large-v2` - 更慢，精度更高
- `large-v3-turbo` - 最新模型，推荐使用

## 日志文件

客户端会生成以下日志文件：
- `whisper_client.log` - 详细的处理日志
- 包含转换进度、API调用、错误信息等

## 故障排除

### 常见问题

1. **ffmpeg未找到**
   ```bash
   # 检查是否安装
   ffmpeg -version
   
   # 安装ffmpeg
   brew install ffmpeg  # macOS
   ```

2. **服务器连接失败**
   ```bash
   # 检查服务器状态
   curl http://localhost:8000/health
   
   # 检查服务器是否运行
   ps aux | grep whisper
   ```

3. **音频转换失败**
   - 检查视频文件是否损坏
   - 确认ffmpeg支持该视频格式
   - 查看详细错误日志

4. **任务提交失败**
   - 检查服务器任务池是否满
   - 确认网络连接正常
   - 检查音频文件大小是否过大

### 性能优化

1. **轮询间隔调优**：
   - 快速网络：`--processing-poll-interval 3 --pending-poll-interval 10`
   - 慢速网络：`--processing-poll-interval 10 --pending-poll-interval 30`
   - 减少服务器负载：增加轮询间隔
   - 提高响应速度：减少轮询间隔

2. **模型选择**：
   - 快速处理：使用`base`或`small`模型
   - 高精度：使用`large-v3-turbo`模型

3. **网络优化**：
   - 使用本地服务器减少网络延迟
   - 检查网络带宽是否足够

4. **服务器配置**：
   - 适当调整服务器任务池大小
   - 确保服务器有足够的内存和计算资源

## 注意事项

1. **文件覆盖**：已存在的`.srt`文件会被跳过，不会覆盖
2. **音频清理**：默认删除临时音频文件，使用`--keep-audio`保留
3. **中断恢复**：可以中断后重新运行，会跳过已处理的文件
4. **大文件处理**：大视频文件转换和上传需要更多时间
5. **服务器限制**：注意服务器的任务池大小限制

## 示例场景

### 批量处理电影
```bash
python whisper_client.py \
  --scan-dir ~/Movies \
  --model large-v3-turbo
```

### 处理学习视频
```bash
python whisper_client.py \
  --scan-dir ~/Education \
  --model small \
  --keep-files
```

### 单文件测试
```bash
python whisper_client.py \
  --single ~/test.mp4 \
  --model tiny
``` 