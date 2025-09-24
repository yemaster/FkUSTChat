import requests
import time
import random
import json
from os import path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    def get_response(self, prompt, stream=False, with_search=False):
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
            'with_search': with_search,
        }

        if stream:
            def generate():
                while True:
                    with requests.post('https://chat.ustc.edu.cn/ms-api/chat-messages', cookies=cookies, headers=headers, json=json_data, stream=True) as response:
                        if response.status_code == 200:
                            for line in response.iter_lines(decode_unicode=True):
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
                        for line in response.iter_lines(decode_unicode=True):
                            if line:
                                if line.startswith("data: "):
                                    line = line[6:]
                                    try:
                                        data = json.loads(line)
                                        object_type = data.get('object', '')
                                        if object_type == 'chat.completion.chunk':
                                            new_content = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                            if isinstance(new_content, str):
                                                answer += new_content
                                                # print(new_content, end='', flush=True)
                                    except Exception as e:
                                        pass
                                    if "id" in data:
                                        answer_id = data.get('id', '')
                                if line == "[DONE]":
                                    break
                        return {
                            "id": answer_id,
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": self.name,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "content": answer
                                    },
                                    "finish_reason": "stop"
                                }
                            ]
                        }
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
        options = webdriver.EdgeOptions()
        service = webdriver.EdgeService(executable_path=path.join(path.dirname(__file__), "../dependencies/msedgedriver.exe"))
        driver = webdriver.Edge(service=service, options=options)
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
            # print(self.config)
            username = self.config.get('username')
            password = self.config.get('password')
            # print(username, password)
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