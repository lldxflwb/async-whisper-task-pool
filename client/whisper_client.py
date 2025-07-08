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
import zipfile
import tempfile
import shutil
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# 添加父目录到路径以便导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class FileEncryptor:
    """文件加密器"""
    
    @staticmethod
    def _generate_key(password: str, salt: bytes) -> bytes:
        """根据密码和盐生成密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    @staticmethod
    def encrypt_file(file_path: str, password: str) -> str:
        """加密文件"""
        try:
            salt = os.urandom(16)
            key = FileEncryptor._generate_key(password, salt)
            fernet = Fernet(key)
            
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            encrypted_data = fernet.encrypt(file_data)
            
            # 将盐和加密数据组合
            combined_data = salt + encrypted_data
            
            encrypted_file_path = file_path + '.enc'
            with open(encrypted_file_path, 'wb') as file:
                file.write(combined_data)
            
            return encrypted_file_path
        except Exception as e:
            raise Exception(f"File encryption failed: {e}")

class WhisperClient:
    """Whisper转录API客户端"""
    
    def __init__(self, server_url: str, scan_dir: str, output_dir: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.scan_dir = Path(scan_dir)
        self.output_dir = Path(output_dir) if output_dir else self.scan_dir
        self.password = "whisper-task-password"  # 任务加密密码
        
        # 创建临时工作目录（在客户端脚本目录）
        self.temp_dir = Path("temp_whisper_work")
        self.temp_dir.mkdir(exist_ok=True)
        
        # 支持的视频格式
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4v', '.webm'}
        
        self._setup_logging()
        self._check_ffmpeg()
    
    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger('WhisperClient')
        self.logger.setLevel(logging.INFO)
        
        # 清除已有的处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            self.logger.info("✓ ffmpeg可用")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("❌ ffmpeg不可用，请安装ffmpeg")
            sys.exit(1)
    
    def check_server_health(self) -> bool:
        """检查服务器健康状态"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            if response.status_code == 200:
                self.logger.info("✓ 服务器连接正常")
                return True
            else:
                self.logger.error(f"❌ 服务器响应异常: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 服务器连接失败: {e}")
            return False
    
    def scan_video_files(self) -> List[Path]:
        """扫描目录中的视频文件"""
        video_files = []
        
        for video_path in self.scan_dir.rglob('*'):
            if video_path.is_file() and video_path.suffix.lower() in self.video_extensions:
                # 检查是否已有字幕文件
                srt_path = video_path.with_suffix('.srt')
                if not srt_path.exists():
                    video_files.append(video_path)
                else:
                    self.logger.info(f"⏭️ 跳过已有字幕的文件: {video_path.name}")
        
        self.logger.info(f"找到 {len(video_files)} 个需要处理的视频文件")
        return video_files
    
    def convert_to_audio(self, video_path: Path) -> Optional[Path]:
        """转换视频为音频（保存到临时目录）"""
        # 生成唯一的临时文件名
        safe_name = "".join(c for c in video_path.stem if c.isalnum() or c in (' ', '-', '_')).rstrip()
        audio_path = self.temp_dir / f"{safe_name}_{video_path.name}.ogg"
        temp_audio_path = self.temp_dir / f"temp_{audio_path.name}"
        
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
    
    def create_task_zip(self, audio_path: Path, task_id: str, model: str) -> Optional[Path]:
        """创建任务压缩包（保存到临时目录）"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 创建metadata
                metadata = {
                    "task_id": task_id,
                    "filename": audio_path.name,
                    "password": self.password,
                    "model": model
                }
                
                # 保存metadata到JSON文件
                metadata_path = os.path.join(temp_dir, 'metadata.json')
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                
                # 复制音频文件并重命名为audio.ogg
                audio_dest = os.path.join(temp_dir, 'audio.ogg')
                shutil.copy2(audio_path, audio_dest)
                
                # 创建ZIP文件（保存到临时目录）
                zip_path = self.temp_dir / f"{task_id}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(metadata_path, 'metadata.json')
                    zipf.write(audio_dest, 'audio.ogg')
                
                # 加密ZIP文件
                encrypted_zip_path = FileEncryptor.encrypt_file(str(zip_path), self.password)
                
                # 删除原始ZIP文件
                os.remove(zip_path)
                
                # 移动加密文件到最终位置
                final_zip_path = self.temp_dir / f"{task_id}.zip.enc"
                shutil.move(encrypted_zip_path, final_zip_path)
                
                self.logger.info(f"✓ 任务包创建完成: {final_zip_path.name}")
                return final_zip_path
                
        except Exception as e:
            self.logger.error(f"❌ 创建任务包失败: {e}")
            return None
    
    def submit_task(self, zip_path: Path, task_id: str) -> bool:
        """提交任务包到服务器"""
        try:
            # 准备表单数据
            data = {
                'task_id': task_id
            }
            
            # 准备文件
            with open(zip_path, 'rb') as f:
                files = {'task_file': (f'{task_id}.zip.enc', f, 'application/octet-stream')}
                
                response = requests.post(
                    f"{self.server_url}/tasks/submit",
                    data=data,
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✓ 任务提交成功: {task_id}")
                    return True
                else:
                    self.logger.error(f"❌ 任务提交失败: {result.get('message', '未知错误')}")
                    return False
            else:
                self.logger.error(f"❌ 任务提交失败: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 网络请求失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ 提交任务异常: {e}")
            return False
    
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
    
    def cleanup_temp_files(self, audio_path: Path, zip_path: Path):
        """清理临时文件"""
        try:
            if audio_path.exists():
                audio_path.unlink()
                self.logger.info(f"清理音频文件: {audio_path.name}")
            
            if zip_path.exists():
                zip_path.unlink()
                self.logger.info(f"清理任务包: {zip_path.name}")
        except Exception as e:
            self.logger.warning(f"清理临时文件失败: {e}")
    
    def cleanup_temp_dir(self):
        """清理临时工作目录"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"清理临时目录: {self.temp_dir}")
        except Exception as e:
            self.logger.warning(f"清理临时目录失败: {e}")
    
    def process_single_video(self, video_path: Path, model: str = "large-v3", 
                           keep_files: bool = False) -> bool:
        """处理单个视频文件"""
        self.logger.info(f"开始处理: {video_path}")
        
        # 1. 转换为音频（保存到临时目录）
        audio_path = self.convert_to_audio(video_path)
        if not audio_path:
            return False
        
        task_id = str(uuid.uuid4())
        zip_path = None
        
        try:
            # 2. 创建任务包（保存到临时目录）
            zip_path = self.create_task_zip(audio_path, task_id, model)
            if not zip_path:
                return False
            
            # 3. 提交任务
            if not self.submit_task(zip_path, task_id):
                return False
            
            # 4. 等待结果
            srt_content = self.wait_for_result(task_id)
            if not srt_content:
                return False
            
            # 5. 保存字幕文件（到视频目录）
            success = self.save_srt_file(video_path, srt_content)
            
            return success
            
        finally:
            # 6. 清理临时文件（除非指定保留）
            if not keep_files and audio_path and zip_path:
                self.cleanup_temp_files(audio_path, zip_path)
    
    def process_all_videos(self, model: str = "large-v3", 
                          max_workers: int = 2, keep_files: bool = False) -> Dict[str, bool]:
        """处理所有视频文件"""
        video_files = self.scan_video_files()
        if not video_files:
            self.logger.info("没有找到需要处理的视频文件")
            return {}
        
        results = {}
        
        try:
            # 使用线程池处理多个文件
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_video = {
                    executor.submit(self.process_single_video, video_path, model, keep_files): video_path
                    for video_path in video_files
                }
                
                # 等待任务完成
                for future in future_to_video:
                    video_path = future_to_video[future]
                    try:
                        success = future.result()
                        results[str(video_path)] = success
                        status = "✓" if success else "❌"
                        self.logger.info(f"{status} {video_path.name}: {'成功' if success else '失败'}")
                    except Exception as e:
                        self.logger.error(f"❌ 处理 {video_path.name} 时发生异常: {e}")
                        results[str(video_path)] = False
        
        finally:
            # 清理临时目录（除非指定保留）
            if not keep_files:
                self.cleanup_temp_dir()
        
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
    parser.add_argument("--model", default="large-v3",
                       help="Whisper模型 (默认: large-v3)")
    parser.add_argument("--max-workers", type=int, default=2,
                       help="最大并发任务数 (默认: 2)")
    parser.add_argument("--keep-files", action="store_true",
                       help="保留转换的音频和任务包文件")
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
                video_path, args.model, args.keep_files
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
                keep_files=args.keep_files
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