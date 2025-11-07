import requests
import time
import random
import json
from os import path
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from adapters.base import FkUSTChat_BaseAdapter, FkUSTChat_BaseModel

def get_random_queue_code():
    # return a random 32-character string
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
    return ''.join(random.choice(chars) for _ in range(32))

class USTC_Base_Model(FkUSTChat_BaseModel):
    def __init__(self, adapter, model, model_info):
        """
        Initializes the USTC_DeepSeek_Model with the given adapter and model information.
        
        :param adapter: The adapter instance to which this model belongs.
        :param model_info: Information about the model, such as its name and configuration.
        """
        super().__init__(adapter, model_info)

        self.model = model

    def get_response(self, prompt, stream=False, with_search=False, tools=[]):
        credentials = self.adapter.get_credentials()
        queue_code = self.adapter.enter_queue()

        cookies = {
            '_ga_Q8WSZQS8E1': 'GS2.1.s1757597943$o7$g0$t1757597943$j60$l0$h1338098571',
            '_ga': 'GA1.1.1970297231.1750309927',
            '_ga_PG4WGSYP0Y': 'GS2.1.s1758189290$o2$g1$t1758192312$j60$l0$h0',
            '_ga_HYDB8XD6M6': 'GS2.1.s1758189297$o13$g1$t1758192312$j60$l0$h0',
        }

        headers = {
            'accept': 'text/event-stream, */*',
            'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5',
            'authorization': f'Bearer {credentials}',
            'content-type': 'application/json',
            'dnt': '1',
            'origin': 'https://chat.ustc.edu.cn',
            'priority': 'u=1, i',
            'referer': 'https://chat.ustc.edu.cn/ustchat/',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
        }

        json_data = {
            'messages': prompt,
            'queue_code': queue_code,
            'model': self.model,
            'stream': True,
            'with_search': with_search
        }
        if self.allow_tool and len(tools):
            json_data["tools"] = tools

        # print(f'[+] Deal with Chat: {prompt}')

        if stream:
            def generate():
                while True:
                    with requests.post('https://chat.ustc.edu.cn/ms-api/chat-messages', cookies=cookies, headers=headers, json=json_data, stream=True) as response:
                        if response.status_code == 200:
                            for line in response.iter_lines(decode_unicode=True):
                                # print(line)
                                if line:
                                    if line.startswith("data: "):
                                        line = line[6:]
                                        yield f"data: {line}\n\n"
                                    if line == "[DONE]":
                                        return
                        else:
                            print(f"Request failed with status code {response.status_code}, text {response.text}, retrying in 3 seconds...")
                            time.sleep(3)
            return generate()
        else:
            while True:
                with requests.post('https://chat.ustc.edu.cn/ms-api/chat-messages', cookies=cookies, headers=headers, json=json_data, stream=True) as response:
                    if response.status_code == 200:
                        answer_id = ""
                        answer = ""
                        tool_calls = {}  # 用字典暂存，key=index
                        final_tool_calls = []  # 最终合并后的结果

                        for line in response.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            if line.startswith("data: "):
                                line = line[6:]
                                if line.strip() == "[DONE]":
                                    break

                                try:
                                    data = json.loads(line)
                                except Exception:
                                    continue

                                if "id" in data:
                                    answer_id = data.get("id", "")

                                if data.get("object") != "chat.completion.chunk":
                                    continue

                                choice = data.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                finish_reason = choice.get("finish_reason")

                                if "content" in delta:
                                    answer += delta["content"]

                                if "tool_calls" in delta:
                                    for tc in delta["tool_calls"]:
                                        index = tc.get("index", 0)
                                        # 初始化对应 index 的 tool_call
                                        if index not in tool_calls:
                                            tool_calls[index] = {
                                                "id": tc.get("id"),
                                                "type": tc.get("type"),
                                                "function": {
                                                    "name": tc.get("function", {}).get("name", ""),
                                                    "arguments": "",
                                                },
                                            }

                                        # 累积 arguments
                                        func = tc.get("function", {})
                                        if "arguments" in func:
                                            tool_calls[index]["function"]["arguments"] += func["arguments"]

                                if finish_reason in ("stop", "tool_calls"):
                                    # 将字典转为按 index 排序的列表
                                    final_tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())]
                                    break

                            elif line.strip() == "[DONE]":
                                break
                            
                        message = {
                            "role": "assistant",
                            "content": answer
                        }
                        
                        if final_tool_calls:
                            message["tool_calls"] = final_tool_calls

                        result = {
                            "id": answer_id,
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": self.name,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": message,
                                    "finish_reason": "stop" if not final_tool_calls else "tool_calls"
                                }
                            ]
                        }
                        # print(result)
                        return result

                    else:
                        print(f"Request failed with status code {response.status_code}, text {response.text}, retrying in 3 seconds...")
                        time.sleep(3)

        
class USTC_DeepSeek_R1_Model(USTC_Base_Model):
    def __init__(self, adapter):
        super().__init__(adapter, "deepseek", {
            "name": "USTC_DeepSeek_r1_Model",
            "show": "USTC Deepseek r1",
            "description": "USTC DeepSeek-r1 Model for FkUSTChat",
            "author": "yemaster"
        })

class USTC_DeepSeek_V3_Model(USTC_Base_Model):
    def __init__(self, adapter):
        super().__init__(adapter, "deepseek-v3", {
            "name": "USTC_DeepSeek_v3_Model",
            "show": "USTC Deepseek v3",
            "description": "USTC DeepSeek-r1 Model for FkUSTChat",
            "author": "yemaster"
        })
        self.allow_tool = True

class USTC_FOOL_Model(USTC_Base_Model):
    def __init__(self, adapter):
        super().__init__(adapter, "whale-23", {
            "name": "USTC_Fool_Model",
            "show": "科大模型 (Qwen)",
            "description": "USTC DeepSeek-r1 Model for FkUSTChat",
            "author": "yemaster"
        })


class USTC_Adapter(FkUSTChat_BaseAdapter):
    def __init__(self, context):
        """
        Initializes the USTC_Adapter with the given context and adapter information.
        
        :param context: The context in which the adapter operates.
        :param adapter_info: Information about the adapter, such as its name and configuration.
        """
        super().__init__(context, {
            "name": "USTC_Adapter",
            "description": "USTC Adapter for FkUSTChat",
            "author": "yemaster"
        })

        self.BACKEND_URL = "https://chat.ustc.edu.cn"

        self.models = {
            "deepseek-r1": USTC_DeepSeek_R1_Model(self),
            "deepseek-v3": USTC_DeepSeek_V3_Model(self),
            "fool": USTC_FOOL_Model(self)
        }

    def configure_format(self):
        return {
            "username": {
                "type": "string",
                "description": "USTC 统一身份认证用户名",
                "required": True
            },
            "password": {
                "type": "string",
                "description": "USTC 统一身份认证密码",
                "required": True
            },
            "credentials": {
                "type": "string",
                "description": "自动获取的 Credential，无需手动填写",
                "required": False
            }
        }


    def is_login(self):
        credentials = self.config.get('credentials', 'none')
        check_url = f"{self.BACKEND_URL}/ms-api/search-app"
        cookies = {
            '_ga_Q8WSZQS8E1': 'GS2.1.s1757597943$o7$g0$t1757597943$j60$l0$h1338098571',
            '_ga': 'GA1.1.1970297231.1750309927',
            '_ga_PG4WGSYP0Y': 'GS2.1.s1758189290$o2$g1$t1758192312$j60$l0$h0',
            '_ga_HYDB8XD6M6': 'GS2.1.s1758189297$o13$g1$t1758192312$j60$l0$h0',
        }
                
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5',
            'authorization': f'Bearer {credentials}',
            'content-type': 'application/json',
            'dnt': '1',
            'origin': 'https://chat.ustc.edu.cn',
            'priority': 'u=1, i',
            'referer': 'https://chat.ustc.edu.cn/ustchat/',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
        }

        json_data = {
            'input': '帮我用 Python 解决这道题',
        }
        response = requests.post(check_url, cookies=cookies, headers=headers, json=json_data)
        if response.status_code != 401:
            return True
        return False

    def do_login(self, username, password):
        if sys.platform.startswith('win32'):
            try:
                edge_driver_path = EdgeChromiumDriverManager().install()
            except:
                edge_driver_path = path.join(path.dirname(__file__), "../dependencies/msedgedriver.exe")
            options = webdriver.EdgeOptions()
            service = webdriver.EdgeService(executable_path=edge_driver_path)
            driver = webdriver.Edge(service=service, options=options)
        elif sys.platform.startswith('darwin'):
            driver = webdriver.Safari()
        else:
            raise SystemError("Unsupported OS.")
        
        driver.maximize_window()

        driver.get("https://id.ustc.edu.cn/cas/login?service=https:%2F%2Fchat.ustc.edu.cn%2Fustchat%2F")

        try:
            user_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='请输入学工号/GID']"))
            )
            pass_input = driver.find_element(By.XPATH, "//input[@placeholder='请输入密码']")

            if username and password:
                user_input.send_keys(username)
                pass_input.send_keys(password)

                login_btn = driver.find_element(By.ID, "submitBtn")
                login_btn.click()
        except Exception as e:
            driver.quit()
            return False
        
        tries = 0
        while True:
            time.sleep(1)
            tries += 1
            if tries > 30:
                return False
            url = driver.current_url
            if url.startswith("https://chat.ustc.edu.cn/ustchat"):
                # 从 localStorage 获取 token
                try:
                    user_store = driver.execute_script("return JSON.parse(window.localStorage.getItem(\"ustchat-user-store\"));")
                    state = user_store.get('state', {})
                    is_login = state.get('isLogin', False)
                    if is_login:
                        token = state.get('token', '')
                        self.set_config('credentials', token)
                        driver.quit()
                        return token
                except Exception as e:
                    pass

    def get_credentials(self):
        if not self.is_login():
            print(self.config)
            username = self.config.get('username')
            password = self.config.get('password')
            print(username, password)
            if not username or not password or username == 'PB********' or password == 'PASSWORD HERE':
                self.set_config('username', 'PB********')
                self.set_config('password', 'PASSWORD HERE')
                raise ValueError("USTC Chat 适配器需要你的科大账号和密码才能登录，请在 ./config 文件中编辑")
            credentials = self.do_login(username, password)
        else:
            credentials = self.config.get('credentials', 'none')
        return credentials
    
    def enter_queue(self):
        credentials = self.get_credentials()
        
        queue_code = get_random_queue_code()

        cookies = {
            '_ga_Q8WSZQS8E1': 'GS2.1.s1757597943$o7$g0$t1757597943$j60$l0$h1338098571',
            '_ga': 'GA1.1.1970297231.1750309927',
            '_ga_PG4WGSYP0Y': 'GS2.1.s1758189290$o2$g1$t1758192312$j60$l0$h0',
            '_ga_HYDB8XD6M6': 'GS2.1.s1758189297$o13$g1$t1758192312$j60$l0$h0',
        }

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5',
            'authorization': f'Bearer {credentials}',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': 'https://chat.ustc.edu.cn/ustchat/',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
        }

        params = {
            'queue_code': queue_code,
        }

        queue_url = f"{self.BACKEND_URL}/ms-api/mei-wei-bu-yong-deng"
        response = requests.get(queue_url, params=params, cookies=cookies, headers=headers)
        # print(f"Enter queue response: {response.status_code}, text: {response.text}")

        return queue_code