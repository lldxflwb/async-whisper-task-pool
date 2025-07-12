# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an asynchronous Whisper-based audio transcription service with separate client and server components written in Python. The system processes video files by converting them to audio, uploading encrypted packages to a FastAPI server, and using the Whisper command-line tool for speech-to-text transcription.

## Common Commands

### Server Development
```bash
# Activate environment (documented path)
source ~/Documents/envs/ai/bin/activate

# Install server dependencies
cd server
pip install -r requirements.txt

# Start server (production)
./start_server.sh

# Start server (development)
python main.py --reload --log-level debug

# Test Whisper functionality
python test_whisper.py /path/to/audio.ogg

# Check server health
curl http://localhost:6006/health
```

### Client Development
```bash
# Install client dependencies
cd client
pip install -r requirements.txt

# Run client interactively
python run_client.py

# Run client with parameters
python whisper_client.py --scan-dir /path/to/videos --server-url http://localhost:6006

# Test client
python test_client.py
```

### SRT Post-Processing
```bash
# Clean SRT files (from script directory)
cd script
python srt_cleaner.py --input /path/to/file.srt
python run_cleaner.py  # Interactive mode
```

## Architecture

### Core Components

1. **Server (`server/`)**: FastAPI-based asynchronous API server
   - `api.py`: Main FastAPI application with HTTP endpoints
   - `task_manager.py`: Task pool management and queuing system
   - `whisper_worker.py`: Asynchronous worker using Whisper CLI tool
   - `models.py`: Pydantic data models for API contracts
   - `config.py`: Environment-based configuration management
   - `utils.py`: File handling, encryption, and utilities

2. **Client (`client/`)**: Python client for batch video processing
   - `whisper_client.py`: Main client with video scanning and upload logic
   - `run_client.py`: Interactive configuration wrapper
   - Smart polling: 5s for processing tasks, 15s for queued tasks

3. **Post-Processing (`script/`)**: SRT subtitle cleaning tools
   - `srt_cleaner.py`: Removes repetitive content from Whisper output
   - `run_cleaner.py`: Batch processing interface

### Data Flow
1. Client scans video files → converts to OGG audio (16kHz, mono, 24k bitrate)
2. Audio packaged in encrypted ZIP with metadata → uploaded to server
3. Server manages task queue → Whisper CLI processes audio → generates SRT
4. Client polls for results → downloads and saves SRT files
5. Optional post-processing cleans repetitive content

### Key Technologies
- **Server**: FastAPI, uvicorn, asyncio, cryptography (Fernet), aiofiles
- **Client**: requests, ffmpeg (via subprocess), concurrent.futures
- **Processing**: Whisper CLI tool, not Python library
- **Encryption**: PBKDF2 + Fernet with fixed password: `whisper-task-password`

## Environment Configuration

Server uses `.env` file in `server/` directory:
```bash
MAX_TASK_POOL_SIZE=5
UPLOAD_DIR=uploads
RESULT_DIR=results  
TEMP_DIR=temp
WHISPER_MODEL=large-v3
HOST=0.0.0.0
PORT=6006
RESULT_RETENTION_HOURS=24
```

## Testing and Verification

- No automated test framework - manual testing required
- Server: Use `test_whisper.py` to verify Whisper CLI availability
- Client: Use `test_client.py` for connection testing  
- Health check endpoint: `GET /health`
- Check logs: `whisper_api.log` (server), `whisper_client.log` (client)

## Whisper Models

Supported models: tiny, base, small, medium, large, large-v1, large-v2, large-v3
- Models download automatically on first use
- Use `whisper --help` to verify CLI installation
- Install with: `pip install openai-whisper`

## File Formats

- **Input**: MP4, AVI, MKV, MOV, WMV, FLV, M4V, WEBM
- **Audio**: OGG format (converted via ffmpeg)
- **Output**: SRT subtitle files
- **Encryption**: ZIP with PBKDF2+Fernet encryption

## Performance Tuning

- Adjust `MAX_TASK_POOL_SIZE` based on server CPU/memory
- Client `--max-workers` for concurrent processing (default: 2)
- Polling intervals: `--processing-poll-interval` and `--pending-poll-interval`
- Use local network to reduce latency