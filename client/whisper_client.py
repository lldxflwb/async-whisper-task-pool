#!/usr/bin/env python3
"""
Whisper转录API客户端
自动扫描视频文件，转换为音频并提交转录任务
"""

import os
import sys
import subprocess
import uuid
import time
import json
import requests
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

# 添加父目录到路径以便导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class WhisperClient:
    """Whisper转录API客户端"""
    
    def __init__(self, server_url: str, scan_dir: str, output_dir: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.scan_dir = Path(scan_dir)
        self.output_dir = Path(output_dir) if output_dir else self.scan_dir
        self.password = "whisper_client_" + str(uuid.uuid4())[:8]
        
        # 支持的视频格式
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        # 设置日志
        self._setup_logging()
        
        # 检查ffmpeg
        self._check_ffmpeg()
    
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('whisper_client.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            self.logger.info("✓ ffmpeg可用")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("❌ ffmpeg未找到或不可用，请先安装ffmpeg")
            sys.exit(1)
    
    def check_server_health(self) -> bool:
        """检查服务器健康状态"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            if response.status_code == 200:
                self.logger.info("✓ 服务器连接正常")
                return True
            else:
                self.logger.error(f"❌ 服务器响应异常: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 无法连接到服务器: {e}")
            return False
    
    def scan_video_files(self) -> List[Path]:
        """扫描目录中的视频文件"""
        self.logger.info(f"扫描目录: {self.scan_dir}")
        
        if not self.scan_dir.exists():
            self.logger.error(f"目录不存在: {self.scan_dir}")
            return []
        
        video_files = []
        for file_path in self.scan_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.video_extensions:
                # 检查是否已有对应的srt文件
                srt_path = file_path.with_suffix('.srt')
                if not srt_path.exists():
                    video_files.append(file_path)
                else:
                    self.logger.info(f"跳过已有字幕的文件: {file_path.name}")
        
        self.logger.info(f"找到 {len(video_files)} 个需要处理的视频文件")
        return video_files
    
    def convert_to_audio(self, video_path: Path) -> Optional[Path]:
        """使用ffmpeg将视频转换为音频"""
        audio_path = video_path.with_suffix('.ogg')
        temp_audio_path = audio_path.with_name(f"temp_{audio_path.name}")
        
        try:
            self.logger.info(f"转换音频: {video_path.name}")
            
            # ffmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # 不包含视频
                '-acodec', 'libopus',  # 使用opus编码
                '-ar', '16000',  # 采样率16kHz
                '-ac', '1',  # 单声道
                '-b:a', '24k',  # 比特率24k
                '-y',  # 覆盖输出文件
                str(temp_audio_path)
            ]
            
            # 执行转换
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                # 转换成功，重命名临时文件
                temp_audio_path.rename(audio_path)
                self.logger.info(f"✓ 音频转换完成: {audio_path.name}")
                return audio_path
            else:
                self.logger.error(f"❌ 音频转换失败: {video_path.name}")
                self.logger.error(f"ffmpeg错误: {result.stderr}")
                # 清理临时文件
                if temp_audio_path.exists():
                    temp_audio_path.unlink()
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ 音频转换超时: {video_path.name}")
            if temp_audio_path.exists():
                temp_audio_path.unlink()
            return None
        except Exception as e:
            self.logger.error(f"❌ 音频转换异常: {video_path.name}, 错误: {e}")
            if temp_audio_path.exists():
                temp_audio_path.unlink()
            return None
    
    def submit_task(self, audio_path: Path, model: str = "large-v3-turbo") -> Optional[str]:
        """提交转录任务"""
        task_id = str(uuid.uuid4())
        
        try:
            # 准备表单数据
            data = {
                'task_id': task_id,
                'password': self.password,
                'model': model
            }
            
            # 准备文件
            with open(audio_path, 'rb') as f:
                files = {'audio_file': ('audio.ogg', f, 'audio/ogg')}
                
                response = requests.post(
                    f"{self.server_url}/tasks/submit",
                    data=data,
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✓ 任务提交成功: {audio_path.name} -> {task_id}")
                    return task_id
                else:
                    self.logger.error(f"❌ 任务提交失败: {result.get('message', '未知错误')}")
                    return None
            else:
                self.logger.error(f"❌ 任务提交失败: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 网络请求失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"❌ 提交任务异常: {e}")
            return None
    
    def wait_for_result(self, task_id: str, timeout: int = 600) -> Optional[str]:
        """等待任务完成并获取结果"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 检查任务结果
                response = requests.get(
                    f"{self.server_url}/tasks/{task_id}/result",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('srt_content'):
                        self.logger.info(f"✓ 任务完成: {task_id}")
                        return result['srt_content']
                    elif result.get('status') == 'failed':
                        self.logger.error(f"❌ 任务失败: {task_id}")
                        return None
                else:
                    # 任务可能还在处理中或已被清理
                    pass
                
                # 等待一段时间再检查
                time.sleep(5)
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"检查任务状态时网络错误: {e}")
                time.sleep(10)
        
        self.logger.error(f"❌ 任务超时: {task_id}")
        return None
    
    def save_srt_file(self, video_path: Path, srt_content: str) -> bool:
        """保存SRT字幕文件到视频目录"""
        try:
            srt_path = video_path.with_suffix('.srt')
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            self.logger.info(f"✓ 字幕文件已保存: {srt_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存字幕文件失败: {e}")
            return False
    
    def cleanup_audio_file(self, audio_path: Path):
        """清理临时音频文件"""
        try:
            if audio_path.exists():
                audio_path.unlink()
                self.logger.info(f"清理音频文件: {audio_path.name}")
        except Exception as e:
            self.logger.warning(f"清理音频文件失败: {e}")
    
    def process_single_video(self, video_path: Path, model: str = "large-v3-turbo", 
                           keep_audio: bool = False) -> bool:
        """处理单个视频文件"""
        self.logger.info(f"开始处理: {video_path}")
        
        # 1. 转换为音频
        audio_path = self.convert_to_audio(video_path)
        if not audio_path:
            return False
        
        try:
            # 2. 提交任务
            task_id = self.submit_task(audio_path, model)
            if not task_id:
                return False
            
            # 3. 等待结果
            srt_content = self.wait_for_result(task_id)
            if not srt_content:
                return False
            
            # 4. 保存字幕文件
            success = self.save_srt_file(video_path, srt_content)
            
            return success
            
        finally:
            # 5. 清理音频文件（除非指定保留）
            if not keep_audio:
                self.cleanup_audio_file(audio_path)
    
    def process_all_videos(self, model: str = "large-v3-turbo", 
                          max_workers: int = 2, keep_audio: bool = False) -> Dict[str, bool]:
        """处理所有视频文件"""
        video_files = self.scan_video_files()
        if not video_files:
            self.logger.info("没有找到需要处理的视频文件")
            return {}
        
        results = {}
        
        # 使用线程池处理多个文件
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_video = {
                executor.submit(self.process_single_video, video_path, model, keep_audio): video_path
                for video_path in video_files
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_video):
                video_path = future_to_video[future]
                try:
                    success = future.result()
                    results[str(video_path)] = success
                    if success:
                        self.logger.info(f"✅ 处理成功: {video_path.name}")
                    else:
                        self.logger.error(f"❌ 处理失败: {video_path.name}")
                except Exception as e:
                    self.logger.error(f"❌ 处理异常: {video_path.name}, 错误: {e}")
                    results[str(video_path)] = False
        
        # 统计结果
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        self.logger.info(f"处理完成: {success_count}/{total_count} 个文件成功")
        
        return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Whisper转录客户端")
    parser.add_argument("--server", default="http://localhost:8000", 
                       help="Whisper API服务器地址 (默认: http://localhost:8000)")
    parser.add_argument("--scan-dir", required=True,
                       help="要扫描的视频文件目录")
    parser.add_argument("--output-dir", 
                       help="字幕文件输出目录 (默认: 与视频文件同目录)")
    parser.add_argument("--model", default="large-v3-turbo",
                       help="Whisper模型 (默认: large-v3-turbo)")
    parser.add_argument("--max-workers", type=int, default=2,
                       help="最大并发任务数 (默认: 2)")
    parser.add_argument("--keep-audio", action="store_true",
                       help="保留转换的音频文件")
    parser.add_argument("--single", 
                       help="只处理指定的单个视频文件")
    
    args = parser.parse_args()
    
    # 创建客户端
    client = WhisperClient(
        server_url=args.server,
        scan_dir=args.scan_dir,
        output_dir=args.output_dir
    )
    
    # 检查服务器连接
    if not client.check_server_health():
        print("❌ 无法连接到服务器，请检查服务器是否运行")
        sys.exit(1)
    
    try:
        if args.single:
            # 处理单个文件
            video_path = Path(args.single)
            if not video_path.exists():
                print(f"❌ 文件不存在: {video_path}")
                sys.exit(1)
            
            success = client.process_single_video(
                video_path, args.model, args.keep_audio
            )
            
            if success:
                print(f"✅ 处理成功: {video_path}")
            else:
                print(f"❌ 处理失败: {video_path}")
                sys.exit(1)
        else:
            # 处理所有文件
            results = client.process_all_videos(
                model=args.model,
                max_workers=args.max_workers,
                keep_audio=args.keep_audio
            )
            
            if not results:
                print("没有找到需要处理的文件")
            else:
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                print(f"处理完成: {success_count}/{total_count} 个文件成功")
                
                if success_count < total_count:
                    sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n用户中断处理")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 