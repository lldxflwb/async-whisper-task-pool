import os
import zipfile
import json
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import tempfile
import shutil
from models import TaskMetadata
from config import config

logger = logging.getLogger(__name__)

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
            logger.error(f"File encryption failed: {e}")
            raise
    
    @staticmethod
    def decrypt_file(encrypted_file_path: str, password: str, output_path: str) -> str:
        """解密文件"""
        try:
            with open(encrypted_file_path, 'rb') as file:
                combined_data = file.read()
            
            # 分离盐和加密数据
            salt = combined_data[:16]
            encrypted_data = combined_data[16:]
            
            key = FileEncryptor._generate_key(password, salt)
            fernet = Fernet(key)
            
            decrypted_data = fernet.decrypt(encrypted_data)
            
            with open(output_path, 'wb') as file:
                file.write(decrypted_data)
            
            return output_path
        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise

class ZipFileHandler:
    """ZIP文件处理器"""
    
    @staticmethod
    def create_task_zip(metadata: TaskMetadata, audio_file_path: str, password: str) -> str:
        """创建任务ZIP文件"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存metadata到JSON文件
                metadata_path = os.path.join(temp_dir, 'metadata.json')
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata.dict(), f, ensure_ascii=False, indent=2, default=str)
                
                # 复制音频文件并重命名为audio.ogg
                audio_dest = os.path.join(temp_dir, 'audio.ogg')
                shutil.copy2(audio_file_path, audio_dest)
                
                # 创建ZIP文件
                zip_path = os.path.join(config.UPLOAD_DIR, f"{metadata.task_id}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(metadata_path, 'metadata.json')
                    zipf.write(audio_dest, 'audio.ogg')
                
                # 加密ZIP文件
                encrypted_zip_path = FileEncryptor.encrypt_file(zip_path, password)
                
                # 删除原始ZIP文件
                os.remove(zip_path)
                
                return encrypted_zip_path
        except Exception as e:
            logger.error(f"Create task zip failed: {e}")
            raise
    
    @staticmethod
    def extract_task_zip(encrypted_zip_path: str, password: str) -> Dict[str, Any]:
        """解压任务ZIP文件"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 解密ZIP文件
                decrypted_zip_path = os.path.join(temp_dir, 'decrypted.zip')
                FileEncryptor.decrypt_file(encrypted_zip_path, password, decrypted_zip_path)
                
                # 解压ZIP文件
                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)
                
                with zipfile.ZipFile(decrypted_zip_path, 'r') as zipf:
                    zipf.extractall(extract_dir)
                
                # 读取metadata
                metadata_path = os.path.join(extract_dir, 'metadata.json')
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # 获取音频文件路径
                audio_path = os.path.join(extract_dir, 'audio.ogg')
                
                if not os.path.exists(audio_path):
                    raise FileNotFoundError("Audio file not found in zip")
                
                return {
                    'metadata': metadata,
                    'audio_path': audio_path,
                    'extract_dir': extract_dir
                }
        except Exception as e:
            logger.error(f"Extract task zip failed: {e}")
            raise

class FileManager:
    """文件管理器"""
    
    @staticmethod
    def ensure_directories():
        """确保必要的目录存在"""
        config.ensure_directories()
    
    @staticmethod
    def save_result(task_id: str, srt_content: str) -> str:
        """保存结果文件"""
        try:
            result_path = os.path.join(config.RESULT_DIR, f"{task_id}.srt")
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            return result_path
        except Exception as e:
            logger.error(f"Save result failed: {e}")
            raise
    
    @staticmethod
    def read_result(task_id: str) -> Optional[str]:
        """读取结果文件"""
        try:
            result_path = os.path.join(config.RESULT_DIR, f"{task_id}.srt")
            if os.path.exists(result_path):
                with open(result_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            logger.error(f"Read result failed: {e}")
            return None
    
    @staticmethod
    def cleanup_task_files(task_id: str, zip_file_path: Optional[str] = None):
        """清理任务相关文件"""
        try:
            # 清理压缩文件
            if zip_file_path and os.path.exists(zip_file_path):
                os.remove(zip_file_path)
                logger.info(f"Cleaned up zip file: {zip_file_path}")
            
            # 清理结果文件
            result_path = os.path.join(config.RESULT_DIR, f"{task_id}.srt")
            if os.path.exists(result_path):
                os.remove(result_path)
                logger.info(f"Cleaned up result file: {result_path}")
                
        except Exception as e:
            logger.error(f"Cleanup task files failed: {e}")
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """获取文件大小"""
        try:
            return os.path.getsize(file_path)
        except Exception:
            return 0

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('whisper_api.log'),
            logging.StreamHandler()
        ]
    ) 