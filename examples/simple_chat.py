import requests
import json

# 配置信息
API_BASE = "http://127.0.0.1:5000"
API_KEY = "i love ustc"  # 可以任意填写

def chat_completion():
    """基础聊天对话示例"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": "__USTC_Adapter__deepseek-v3",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "stream": False
    }
    
    response = requests.post(f"{API_BASE}/v1/chat/completions", 
                           headers=headers, json=data)
    return response.json()

print(chat_completion())