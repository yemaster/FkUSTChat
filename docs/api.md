## API 接口文档

### 1. 首页访问

#### 接口描述

访问系统首页，返回前端页面（供浏览器访问）

#### 请求信息

- 路径：`/`
- 方法：GET
- 请求参数：无

#### 响应信息

- 响应类型：text/html
- 响应内容：系统前端页面（index.html）
- 状态码：200 OK

### 2. 查询适配器列表

#### 接口描述

获取系统已加载的所有适配器信息

#### 请求信息

- 路径：`/v1/adapters`
- 方法：GET
- 请求参数：无

#### 响应信息

- 响应类型：application/json
- 状态码：200 OK
- 响应格式：

```json
{
  "object": "list",
  "data": [
    {
      "id": "适配器名称",
      "object": "adapter",
      "created": null,
      "owned_by": "适配器作者",
      "permission": [],
      "root": "适配器名称",
      "parent": null
    }
  ]
}
```

- 字段说明：

  | 字段名          | 类型   | 说明                    |
  | --------------- | ------ | ----------------------- |
  | object          | string | 响应类型，固定为 "list" |
  | data            | array  | 适配器列表              |
  | data[].id       | string | 适配器唯一标识（名称）  |
  | data[].owned_by | string | 适配器作者信息          |
  | 其他字段        | -      | 预留字段，暂固定默认值  |

### 3. 查询模型列表

#### 接口描述

获取系统已加载的所有模型信息

#### 请求信息

- 路径：`/v1/models`
- 方法：GET
- 请求参数：无

#### 响应信息

- 响应类型：application/json
- 状态码：200 OK
- 响应格式：

```json
{
  "object": "list",
  "data": [
    {
      "id": "模型唯一标识",
      "show": "模型显示名称",
      "object": "model",
      "created": null,
      "owned_by": "模型所属适配器",
      "permission": [],
      "root": "模型唯一标识",
      "parent": null
    }
  ]
}
```

- 字段说明：

  | 字段名          | 类型   | 说明                       |
  | --------------- | ------ | -------------------------- |
  | object          | string | 响应类型，固定为 "list"    |
  | data            | array  | 模型列表                   |
  | data[].id       | string | 模型唯一标识（调用时使用） |
  | data[].show     | string | 模型显示名称（友好展示）   |
  | data[].owned_by | string | 模型所属适配器名称         |
  | 其他字段        | -      | 预留字段，暂固定默认值     |

### 4. 聊天补全接口

#### 接口描述

核心聊天交互接口，支持流式 / 非流式响应、搜索增强和工具调用

#### 请求信息

- 路径：`/v1/chat/completions`
- 方法：POST
- 请求头：`Content-Type: application/json`
- 请求体参数：

```json
{
  "stream": false,
  "with_search": false,
  "model": "__USTC_Adapter__deepseek-r1",
  "messages": [
    {
      "role": "user",
      "content": "用户提问内容"
    }
  ],
  "tools": []
}
```

- 参数说明：

  | 参数名             | 类型    | 是否必填 | 默认值                      | 说明                                                         |
  | ------------------ | ------- | -------- | --------------------------- | ------------------------------------------------------------ |
  | stream             | boolean | 否       | false                       | 是否启用流式响应：true - 流式（text/event-stream），false - 非流式（JSON） |
  | with_search        | boolean | 否       | false                       | 是否启用搜索增强功能                                         |
  | model              | string  | 是       | __USTC_Adapter__deepseek-r1 | 模型唯一标识（需从 `/v1/models` 接口获取）                   |
  | messages           | array   | 是       | []                          | 聊天消息列表，格式参考 OpenAI 规范                           |
  | messages[].role    | string  | 是       | -                           | 角色：user（用户）、assistant（助手）、system（系统）        |
  | messages[].content | string  | 是       | -                           | 消息内容                                                     |
  | tools              | array   | 否       | []                          | 工具调用配置（预留字段，当前暂不支持复杂工具定义）           |

#### 响应信息

##### 非流式响应（stream=false）

- 响应类型：application/json
- 状态码：200 OK
- 响应格式：

```json
{
  "id": "响应唯一标识",
  "object": "chat.completion",
  "created": 1699999999,
  "model": "使用的模型标识",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "助手回复内容"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

- 字段说明：

  | 字段名                  | 类型   | 说明                                             |
  | ----------------------- | ------ | ------------------------------------------------ |
  | id                      | string | 响应唯一标识                                     |
  | object                  | string | 响应类型，固定为 "chat.completion"               |
  | created                 | number | 响应生成时间戳（秒级）                           |
  | model                   | string | 实际使用的模型标识                               |
  | choices                 | array  | 回复选项列表（默认 1 个）                        |
  | choices[].message       | object | 助手回复消息                                     |
  | choices[].finish_reason | string | 结束原因：stop（正常结束）、length（长度限制）等 |
  | usage                   | object | 令牌使用统计（预留字段）                         |

##### 流式响应（stream=true）

- 响应类型：text/event-stream
- 状态码：200 OK
- 响应格式（SSE 格式）：

```plaintext
data: {"id":"响应唯一标识","object":"chat.completion.chunk","created":1699999999,"model":"使用的模型标识","choices":[{"index":0,"delta":{"role":"assistant","content":"助手回复内容片段1"},"finish_reason":null}]}

data: {"id":"响应唯一标识","object":"chat.completion.chunk","created":1699999999,"model":"使用的模型标识","choices":[{"index":0,"delta":{"content":"助手回复内容片段2"},"finish_reason":null}]}

data: [DONE]
```

- 字段说明：

  | 字段名        | 类型   | 说明                                     |
  | ------------- | ------ | ---------------------------------------- |
  | object        | string | 响应类型，固定为 "chat.completion.chunk" |
  | delta         | object | 增量内容（每次返回部分回复）             |
  | finish_reason | string | 最后一块数据中为 "stop"，其他为 null     |
  | 最后一行      | string | 固定为 "data: [DONE]"，标识流结束        |

## 错误处理

### 通用错误响应格式

```json
{
  "error": {
    "message": "错误描述信息",
    "type": "错误类型",
    "param": "相关参数（如有）",
    "code": "错误码（如有）"
  }
}
```

### 常见错误码

| 状态码 | 错误类型              | 说明                             |
| ------ | --------------------- | -------------------------------- |
| 400    | invalid_request_error | 请求参数错误（如模型不存在）     |
| 500    | server_error          | 服务器内部错误（如模型调用失败） |

### 错误示例

#### 模型不存在（400）

```json
{
  "error": {
    "message": "Model 'invalid-model' not found",
    "type": "invalid_request_error",
    "param": null,
    "code": null
  }
}
```

#### 服务器内部错误（500）

```json
{
  "error": {
    "message": "模型调用失败：连接超时",
    "type": "server_error",
    "param": null,
    "code": null
  }
}
```