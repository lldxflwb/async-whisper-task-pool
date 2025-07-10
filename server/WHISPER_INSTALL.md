# Whisper命令行工具安装说明

## 概述
本项目已修改为使用Whisper命令行工具而非Python库，以获得更好的性能和资源管理。

## 安装Whisper命令行工具

### 方法1：使用pip安装（推荐）
```bash
pip install openai-whisper
```

### 方法2：从源码安装
```bash
pip install git+https://github.com/openai/whisper.git
```

## 验证安装
安装完成后，验证whisper命令是否可用：
```bash
whisper --help
```

## 支持的模型
- tiny
- base
- small
- medium
- large
- large-v2
- large-v3

## 注意事项
1. 首次运行时，whisper会自动下载所需的模型文件
2. 模型文件较大，请确保有足够的磁盘空间和网络带宽
3. 推荐在生产环境中预先下载模型文件

## 预下载模型（可选）
```bash
# 下载指定模型
whisper --model large-v3 /path/to/dummy/audio.wav

# 或者使用Python脚本
python -c "import whisper; whisper.load_model('large-v3')"
``` 