import json
import openai
from typing import List, Dict, Optional
import time

config = {
    'base_url': 'http://127.0.0.1:5000/v1',
    'api_key': 'abababa',  # 可以任意填写
    'model': '__USTC_Adapter__deepseek-r1',
}

# 系统提示词（可根据需求修改角色定位和功能描述）
SYSTEM_PROMPT = f'''
你是一个友好、专业的智能助手，擅长解答各类问题，提供实用信息和帮助。
要求：
1. 回答准确、简洁，避免冗长
2. 保持对话连贯性，记住上下文信息
3. 遇到不确定的问题，如实告知，不编造信息
4. 语气友好、自然，符合日常交流习惯
'''.strip()

class MultiTurnChatAI:
    def __init__(self, config: Dict, system_prompt: str):
        """
        初始化多轮对话AI
        :param config: 配置字典
        :param system_prompt: 系统提示词
        """
        # 初始化OpenAI客户端
        self.client = openai.OpenAI(
            base_url=config['base_url'],
            api_key=config['api_key']
        )
        
        # 保存配置
        self.model = config['model']
        
        # 初始化对话历史（包含系统提示词）
        self.conversation_history: List[Dict] = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 最大历史轮数（防止对话过长）
        self.max_history_turns = 20  # 可根据需求调整

    def add_message(self, role: str, content: str) -> None:
        """
        添加消息到对话历史
        :param role: 角色（user/assistant/system）
        :param content: 消息内容
        """
        self.conversation_history.append({"role": role, "content": content})
        
        # 限制历史轮数（只保留最近的max_history_turns轮对话，不含system prompt）
        if len(self.conversation_history) > self.max_history_turns + 1:
            # 保留system prompt，删除最旧的用户/助手对话对
            self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-self.max_history_turns:]

    def get_response(self, user_input: str) -> Optional[str]:
        """
        获取AI回复
        :param user_input: 用户输入
        :return: AI回复内容（失败返回None）
        """
        if not user_input.strip():
            print("错误：用户输入不能为空！")
            return None
        
        # 添加用户消息到历史
        self.add_message(role="user", content=user_input.strip())
        
        try:
            # 调用LLM获取回复
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                stream=True
            )
            
            print("助手：", end="", flush=True)
            full_reply = ""
            
            # 逐块处理流式响应
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    chunk_content = chunk.choices[0].delta.content
                    full_reply += chunk_content
                    print(chunk_content, end="", flush=True)  # 实时打印每块内容
            
            print()  # 回复结束后换行
            full_reply = full_reply.strip()
            
            # 添加完整回复到历史
            self.add_message(role="assistant", content=full_reply)
            
            return full_reply
        
        except openai.APIConnectionError:
            print("错误：无法连接到API服务，请检查网络连接和base_url是否正确")
            return None
        except openai.APIError as e:
            print(f"错误：API请求失败 - {e}")
            return None
        except openai.AuthenticationError:
            print("错误：API密钥验证失败，请检查api_key是否正确")
            return None
        except openai.Timeout:
            print("错误：请求超时，请稍后再试")
            return None
        except Exception as e:
            print(f"未知错误：{e}")
            return None

    def clear_history(self) -> None:
        """清空对话历史（保留系统提示词）"""
        self.conversation_history = [self.conversation_history[0]]
        print("对话历史已清空！")

    def show_history(self) -> None:
        """显示当前对话历史"""
        print("\n=== 对话历史 ===")
        for msg in self.conversation_history[1:]:  # 跳过system prompt
            role = "用户" if msg["role"] == "user" else "助手"
            print(f"{role}: {msg['content']}")
        print("=== 历史结束 ===\n")

def main():
    """主函数：交互式对话"""
    # 初始化AI
    ai = MultiTurnChatAI(config, SYSTEM_PROMPT)
    
    print("=== 多轮对话AI ===")
    print("提示：")
    print("  1. 直接输入文字进行对话")
    print("  2. 输入 'clear' 清空对话历史")
    print("  3. 输入 'history' 查看对话历史")
    print("  4. 输入 'quit' 或 'exit' 退出程序")
    print("=" * 30 + "\n")
    
    while True:
        # 获取用户输入
        try:
            user_input = input("你：")
        except KeyboardInterrupt:
            print("\n程序已退出")
            break
        except EOFError:
            print("\n程序已退出")
            break
        
        # 处理命令
        user_input_lower = user_input.strip().lower()
        
        if user_input_lower in ["quit", "exit"]:
            print("助手：再见！有任何问题随时来找我～")
            break
        elif user_input_lower == "clear":
            ai.clear_history()
            continue
        elif user_input_lower == "history":
            ai.show_history()
            continue
        
        # 获取AI回复并显示
        print("助手：", end="", flush=True)
        reply = ai.get_response(user_input)
        if reply:
            print(reply)
        print()  # 空行分隔

if __name__ == "__main__":
    main()