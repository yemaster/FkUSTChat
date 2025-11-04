import json
import openai # pip install openai
import subprocess
import sys
from typing import List, Dict, Any
from types import SimpleNamespace
import re

config = {
    'base_url': 'http://127.0.0.1:5000/v1',
    'api_key': '???',
    'model': '__USTC_Adapter__deepseek-v3',
}

SYSTEM_PROMPT = f'''
你是一个具备Python表达式执行能力的AI助手，能够帮助用户进行计算、数据处理等任务。

## 核心能力
1. 多轮对话：记住上下文信息，持续为用户提供连贯的帮助
2. Python表达式执行：当用户需要计算、数据分析或复杂运算时，自动执行Python表达式
3. 安全优先：只执行安全的Python表达式，不执行任何可能危害系统的操作

## 工作流程
1. 使用 get_request 工具获取用户的要求
2. 使用 think 工具进行思考，分析提取用户的核心要求，分点列举
3. 使用 gen_expression 工具将用户要求转化为 Python 表达式
4. 使用 calc 工具给 Python 表达式求值
5. 使用 think 进行思考，全部任务是否正确完成没有出错？是否还有剩余任务没有完成？继续用 gen_expression 工具完成剩余的任务。当你认为全部任务都完成后，用 task_done 工具给出你的答案以及求解过程。

每一步都必须使用对应的工具调用，一定要严格按照要求来！注意，只有你调用 task_done 工具之后，才会结束！你的结果必须使用 task_done 来告诉用户。
'''.strip()

USER_PROMPT = "加油干活吧，记得严格按照要求，每一步都必须使用对应的工具调用"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_request",
            "description": "使用这个工具来获取用户要求。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": "使用这个工具来进行思考，例如进行复杂的推理、头脑风暴、或者分析上一步得到的结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "你思考的内容，不超过 200 字",
                    },
                },
                "required": ["thought"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gen_expression",
            "description": "使用这个工具来将内容翻译为 Python 表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "需要翻译的内容",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "使用这个工具来给 Python 表达式求值",
            "parameters": {
                "type": "object",
                "properties": {
                    "exp": {
                        "type": "string",
                        "description": "需要求值的 Python 表达式",
                    },
                },
                "required": ["exp"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_done",
            "description": "使用这个工具来汇报你的工作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "你的理解和计算结果。",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]

client = openai.AsyncOpenAI(
    base_url=config['base_url'],
    api_key=config['api_key'],
    timeout=30,
)

class SafePythonEvaluator:
    """安全的Python表达式执行器，限制危险操作"""
    
    # 修正：使用字典统一管理允许的内置函数和模块（不再使用set）
    # 结构说明：
    # - 键为函数名或模块名
    # - 值为 None 表示普通内置函数，值为列表表示模块下的允许函数
    ALLOWED_BUILTINS = {
        # 普通内置函数（值为 None 表示直接允许）
        'abs': None,
        'all': None,
        'any': None,
        'bool': None,
        'bytes': None,
        'chr': None,
        'complex': None,
        'dict': None,
        'float': None,
        'int': None,
        'len': None,
        'list': None,
        'max': None,
        'min': None,
        'pow': None,
        'range': None,
        'round': None,
        'set': None,
        'sorted': None,
        'str': None,
        'sum': None,
        'tuple': None,
        'zip': None,
        # 数学相关模块（值为允许的函数列表）
        'math': [
            'acos', 'asin', 'atan', 'atan2', 'ceil', 'cos', 'cosh',
            'degrees', 'e', 'exp', 'fabs', 'floor', 'fmod', 'frexp',
            'hypot', 'inf', 'isclose', 'isfinite', 'isinf', 'isnan',
            'ldexp', 'log', 'log10', 'log1p', 'modf', 'pi', 'pow',
            'radians', 'sin', 'sinh', 'sqrt', 'tan', 'tanh', 'trunc'
        ],
        # 日期相关模块（值为允许的函数列表）
        'datetime': [
            'date', 'datetime', 'time', 'timedelta', 'utcnow', 'now'
        ]
    }
    
    # 禁止的危险操作模式
    FORBIDDEN_PATTERNS = [
        r'import\s+', r'from\s+', r'eval\(', r'exec\(',
        r'__import__', r'open\(', r'file\(', r'subprocess',
        r'os\.', r'sys\.', r'shutil\.', r'pickle',
        r'globals\(', r'locals\(', r'dir\(', r'getattr\(',
        r'setattr\(', r'delattr\(', r'compile\(', r'compile'
    ]
    
    @classmethod
    def is_safe_expression(cls, expr: str) -> bool:
        """检查表达式是否安全"""
        # 去除空白字符进行检查
        clean_expr = re.sub(r'\s+', '', expr)
        
        # 检查禁止模式
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, clean_expr, re.IGNORECASE):
                return False
        
        return True
    
    @classmethod
    def execute(cls, expr: str, timeout: int = 5) -> Dict[str, Any]:
        try:            
            safe_globals = {}
            
            # 1. 添加普通内置函数（值为 None 的键）
            for func_name, _ in cls.ALLOWED_BUILTINS.items():
                if _ is None and hasattr(__builtins__, func_name):
                    safe_globals[func_name] = getattr(__builtins__, func_name)
            
            # 2. 添加允许的模块及其函数
            # 处理 math 模块
            if 'math' in cls.ALLOWED_BUILTINS and isinstance(cls.ALLOWED_BUILTINS['math'], list):
                import math
                safe_globals['math'] = SimpleNamespace(**{
                    func: getattr(math, func) 
                    for func in cls.ALLOWED_BUILTINS['math']
                    if hasattr(math, func)
                })
            
            # 处理 datetime 模块
            if 'datetime' in cls.ALLOWED_BUILTINS and isinstance(cls.ALLOWED_BUILTINS['datetime'], list):
                import datetime
                safe_globals['datetime'] = SimpleNamespace(**{
                    func: getattr(datetime, func) 
                    for func in cls.ALLOWED_BUILTINS['datetime']
                    if hasattr(datetime, func)
                })
            return f"Result: {eval(expr, safe_globals)}"
        except Exception as e:
            return f"Error: {e}"

async def get_response(**kwargs):
    resp = (await client.chat.completions.create(
        model=config['model'],
        **kwargs,
    )).model_dump()
    return resp['choices'][0]

async def gen_expression(content):
    msgs = [
        {'role': 'system', 'content': "你是一个 Python 表达式转换助手，用于将用户命令转换为能够直接用 eval 执行的单个 Python 表达式。你转换的 Python 表达式必须是纯表达式，不能是语句。仅支持数学计算、字符串处理、列表/字典操作、日期计算等，可使用math模块（如math.pi、math.sqrt）和datetime模块的常用函数，math库和datetime库已经导入，禁止执行：文件操作、网络请求、系统命令、模块导入等危险操作。如果你认为你无法处理转换操作，请返回一个字符串，内容为你的理由。你的返回结果必须只能包含单行 Python 表达式，不要输出其他任何多余的字符，只输出表达式即可！"},
        {'role': 'user', 'content': f"帮我把如下内容转换为 Python 表达式：\n{content}"},
    ]
    resp = await get_response(messages=msgs, max_tokens=300, temperature=0, n=1, seed=6)
    # print("resp", resp)
    return resp['message']['content']

async def parse_tool_output(tool_call, webpage_content, alerts):
    def response(msg):
        return {
            'role': 'tool',
            'content': msg,
            'tool_call_id': tool_call['id'],
        }
    
    try:
        tool_args = json.loads(tool_call['function'].get('arguments', 'null'))
    except Exception:
        alerts.append('Agent 错误：无法解析调用参数')
        return

    tool_name = tool_call['function'].get('name', 'null')
    
    if tool_name=='get_request':
        alerts.append('Agent 读取了用户要求')
        return response(f'以下是用户要求：\n<content>\n{webpage_content}\n</content>')
    elif tool_name=='think':
        thought = tool_args['thought']
        alerts.append(f'Agent 思考了 {thought}')
        return response('继续。')
    elif tool_name=='gen_expression':
        content = tool_args['content']
        exp = await gen_expression(content)
        alerts.append(f'Agent 对 {content} 进行了转换，得到表达式 {exp}')
        return response(exp)
    elif tool_name=='calc':
        exp = tool_args['exp']
        res = SafePythonEvaluator().execute(exp)
        alerts.append(f'Agent 对 {exp} 进行了求值，得到结果 {res}')
        return response(res)
    elif tool_name=='task_done':
        alerts.append(f'Agent 完成了任务')
        alerts.append(tool_args.get('summary', '???'))
        return
    else:
        alerts.append(f'Agent 错误：工具 {tool_name} 不存在')
        return
    
async def run_llm(webpage_content):
    msgs = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': USER_PROMPT},
    ]

    while True:
        try:
            resp = await get_response(messages=msgs, tools=TOOLS, tool_choice='required', max_tokens=300, temperature=0, n=1, seed=6)
        except Exception as e:
            yield f'Agent 错误：{type(e)}'
            return
        
        if resp['finish_reason']!='tool_calls':
            yield f'Agent 错误：缺失工具调用 (finish_reason = {resp["finish_reason"]})'
            print(resp['message']['content'])
            return
        
        msgs.append(resp['message'])
        #print('->', resp['message'])
        
        for tool_call in resp['message']['tool_calls']:
            alerts = []
            tool_resp = await parse_tool_output(tool_call, webpage_content, alerts)
            #print('  <-', tool_resp)

            for alert in alerts:
                yield alert
            
            if not tool_resp:
                return

            msgs.append(tool_resp)

async def main():
    webpage = input('> ')
    async for msg in run_llm(webpage):
        print('【', msg, '】')

if __name__=='__main__':
    import asyncio
    asyncio.run(main())
