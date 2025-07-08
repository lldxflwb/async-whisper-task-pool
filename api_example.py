#!/usr/bin/env python3
"""
Whisper转录API客户端使用示例
"""

import requests
import uuid
import time
import json
from pathlib import Path

# 服务器配置
SERVER_URL = "http://localhost:8000"

def check_server_health():
    """检查服务器健康状态"""
    try:
        response = requests.get(f"{SERVER_URL}/health")
        return response.status_code == 200
    except:
        return False

def check_pool_status():
    """检查任务池状态"""
    response = requests.get(f"{SERVER_URL}/pool/status")
    return response.json()

def submit_task(audio_file_path, password="test123", model="large-v3-turbo"):
    """提交转录任务"""
    task_id = str(uuid.uuid4())
    
    # 准备表单数据
    data = {
        'task_id': task_id,
        'password': password,
        'model': model
    }
    
    # 准备文件
    with open(audio_file_path, 'rb') as f:
        files = {'audio_file': ('audio.ogg', f, 'audio/ogg')}
        
        response = requests.post(
            f"{SERVER_URL}/tasks/submit",
            data=data,
            files=files
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"任务提交成功: {result}")
        return task_id
    else:
        print(f"任务提交失败: {response.status_code} - {response.text}")
        return None

def get_task_status(task_id):
    """获取任务状态"""
    response = requests.get(f"{SERVER_URL}/tasks/{task_id}/status")
    if response.status_code == 200:
        return response.json()
    else:
        return None

def get_task_result(task_id):
    """获取任务结果"""
    response = requests.get(f"{SERVER_URL}/tasks/{task_id}/result")
    if response.status_code == 200:
        return response.json()
    else:
        return None

def download_result(task_id, output_path):
    """下载结果文件"""
    response = requests.get(f"{SERVER_URL}/tasks/{task_id}/result/download")
    if response.status_code == 200:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    return False

def clear_task_result(task_id):
    """清除任务结果"""
    response = requests.delete(f"{SERVER_URL}/tasks/{task_id}/result")
    return response.status_code == 200

def wait_for_completion(task_id, timeout=300):
    """等待任务完成"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # 检查任务状态
        status = get_task_status(task_id)
        if status:
            print(f"任务状态: {status['status']}")
            if status['status'] in ['completed', 'failed']:
                return status
        
        # 检查是否有结果
        result = get_task_result(task_id)
        if result and result['srt_content']:
            print("任务完成！")
            return result
        
        time.sleep(2)
    
    print("任务超时")
    return None

def main():
    """主函数"""
    print("Whisper转录API客户端示例")
    print("=" * 50)
    
    # 检查服务器状态
    if not check_server_health():
        print("错误: 服务器不健康或不可访问")
        return
    
    print("✓ 服务器健康")
    
    # 检查任务池状态
    pool_status = check_pool_status()
    print(f"任务池状态: {pool_status}")
    
    # 示例音频文件路径（需要替换为实际的音频文件）
    audio_file_path = "example_audio.ogg"
    
    if not Path(audio_file_path).exists():
        print(f"错误: 音频文件不存在: {audio_file_path}")
        print("请准备一个OGG格式的音频文件")
        return
    
    print(f"提交任务...")
    task_id = submit_task(audio_file_path)
    
    if not task_id:
        print("任务提交失败")
        return
    
    print(f"任务ID: {task_id}")
    
    # 等待任务完成
    print("等待任务完成...")
    result = wait_for_completion(task_id)
    
    if result:
        if 'srt_content' in result and result['srt_content']:
            print("转录结果:")
            print("-" * 50)
            print(result['srt_content'])
            print("-" * 50)
            
            # 下载结果文件
            output_path = f"{task_id}.srt"
            if download_result(task_id, output_path):
                print(f"结果已保存到: {output_path}")
            
            # 清除结果（可选）
            # clear_task_result(task_id)
            # print("结果已清除")
        else:
            print("任务失败或无结果")
    else:
        print("任务未完成")

if __name__ == "__main__":
    main() 