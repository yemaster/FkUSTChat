from flask import Flask, request, jsonify, render_template, Response
import sys
import json

from libs.core import FkUSTChat_Core
from libs.adapter_loader import load_adapter 

app = Flask(__name__)
core = FkUSTChat_Core()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/v1/adapters', methods=['GET'])
def list_adapters():
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": adapter_name,
                "object": "adapter",
                "created": None,
                "owned_by": adapter.author,
                "permission": [],
                "root": adapter_name,
                "parent": None,
            }
            for adapter_name, adapter in core.adapters.items()
        ]
    })

@app.route('/v1/models', methods=['GET'])
def list_models():
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": model_name,
                "show": model.model_info.get('show', model_name),
                "object": "model",
                "created": None,
                "owned_by": model.adapter.name if model.adapter else "unknown",
                "permission": [],
                "root": model_name,
                "parent": None,
            }
            for model_name, model in core.models.items()
        ]
    })

@app.route("/v1/chat/completions", methods=['POST'])
def chat_completions():
    data = request.json
    stream = data.get("stream", False)
    with_search = data.get("with_search", False)
    model = data.get("model", "__USTC_Adapter__deepseek-r1")
    messages = data.get("messages", [])
    tools = data.get("tools", [])

    if model not in core.models:
        return jsonify({
            "error": {
                "message": f"Model '{model}' not found",
                "type": "invalid_request_error",
                "param": None,
                "code": None
            }
        }), 400
    
    try:
        response = core.models[model].get_response(messages, stream=stream, with_search=with_search, tools=tools)
        if stream:
            return Response(response, content_type='text/event-stream')
        else:
            return jsonify(response)
    except Exception as e:
        return jsonify({
            "error": {
                "message": str(e),
                "type": "server_error",
                "param": None,
                "code": None
            }
        }), 500

def claude_to_openai_messages(claude_messages, system=None):
    openai_msgs = []
    if system:
        openai_msgs.append({"role": "system", "content": system})
    
    for msg in claude_messages:
        role = msg["role"]
        content = msg["content"]
        
        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
        elif isinstance(content, list):
            if role == "user":
                for block in content:
                    if block["type"] == "text":
                        openai_msgs.append({"role": "user", "content": block["text"]})
                    elif block["type"] == "tool_result":
                        tool_content = block["content"]
                        if not isinstance(tool_content, str):
                            tool_content = json.dumps(tool_content)
                        openai_msgs.append({
                            "role": "tool",
                            "content": tool_content,
                            "tool_call_id": block["tool_use_id"]
                        })
            elif role == "assistant":
                asst_content = ""
                tool_calls = []
                for block in content:
                    if block["type"] == "text":
                        asst_content += block["text"]
                    elif block["type"] == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"])
                            }
                        })
                openai_msg = {"role": "assistant"}
                if asst_content:
                    openai_msg["content"] = asst_content
                if tool_calls:
                    openai_msg["tool_calls"] = tool_calls
                openai_msgs.append(openai_msg)
    
    return openai_msgs

def claude_to_openai_tools(claude_tools):
    openai_tools = []
    for tool in claude_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {})
            }
        })
    return openai_tools

@app.route("/v1/messages", methods=['POST'])
def messages():
    data = request.json
    model = data.get("model")
    if not model:
        return jsonify({
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "model is required"
            }
        }), 400
    if model not in core.models:
        for model_txt in core.models:
            if model_txt.lower() == model.lower():
                model = model_txt
                break
        else:
            return jsonify({
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Model '{model}' not found"
                }
            }), 400

    claude_messages = data.get("messages")
    if not claude_messages:
        return jsonify({
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "messages is required"
            }
        }), 400

    max_tokens = data.get("max_tokens")
    if max_tokens is None:
        return jsonify({
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "max_tokens is required"
            }
        }), 400

    stream = data.get("stream", False)
    with_search = data.get("with_search", False)
    claude_tools = data.get("tools", [])
    system = data.get("system", None)

    openai_messages = claude_to_openai_messages(claude_messages, system)
    openai_tools = claude_to_openai_tools(claude_tools)

    try:
        openai_response = core.models[model].get_response(openai_messages, stream=stream, with_search=with_search, tools=openai_tools)

        if stream:
            def transform_stream(openai_stream):
                yield 'event: message_start\n'
                yield f'data: {{"type":"message_start", "message":{{"id":"msg_1", "type":"message", "role":"assistant", "content":[], "model":"{model}", "stop_reason":null, "stop_sequence":null, "usage":{{"input_tokens":0, "output_tokens":0}}}}}}\n\n'

                content_index = 0
                tool_indices = {}
                is_text = False
                full_output_tokens = 0
                stop_reason = None
                partial_inputs = {}

                for line in openai_stream:
                    if line.startswith('data: '):
                        chunk_str = line[6:].strip()
                        if chunk_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(chunk_str)
                        except json.JSONDecodeError:
                            continue
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0]["delta"]
                            if "content" in delta and delta["content"] is not None:
                                text = delta["content"]
                                if not is_text:
                                    is_text = True
                                    yield 'event: content_block_start\n'
                                    yield f'data: {{"type":"content_block_start", "index":{content_index}, "content_block":{{"type":"text", "text":""}}}}\n\n'
                                    content_index += 1
                                yield 'event: content_block_delta\n'
                                yield f'data: {{"type":"content_block_delta", "index":{content_index-1}, "delta":{{"type":"text_delta", "text":{json.dumps(text)}}}}}\n\n'
                                full_output_tokens += len(text.split())
                            if "tool_calls" in delta and delta["tool_calls"]:
                                for tc_delta in delta["tool_calls"]:
                                    idx = tc_delta["index"]
                                    if idx not in tool_indices:
                                        tool_indices[idx] = content_index
                                        partial_inputs[idx] = ""
                                        content_index += 1
                                        tc_id = tc_delta.get("id", f"toolu_{idx}")
                                        fn = tc_delta.get("function", {})
                                        name = fn.get("name", "unknown")
                                        yield 'event: content_block_start\n'
                                        yield f'data: {{"type":"content_block_start", "index":{tool_indices[idx]}, "content_block":{{"type":"tool_use", "id":"{tc_id}", "name":"{name}", "input":{{}}}}}}\n\n'
                                    fn = tc_delta.get("function", {})
                                    if "arguments" in fn and fn["arguments"]:
                                        arg_chunk = fn["arguments"]
                                        partial_inputs[idx] += arg_chunk
                                        yield 'event: content_block_delta\n'
                                        yield f'data: {{"type":"content_block_delta", "index":{tool_indices[idx]}, "delta":{{"type":"input_json_delta", "partial_json":{json.dumps(arg_chunk)}}}}}\n\n'
                                        full_output_tokens += len(arg_chunk.split())
                            if "finish_reason" in chunk["choices"][0] and chunk["choices"][0]["finish_reason"]:
                                stop_reason = chunk["choices"][0]["finish_reason"]

                for i in range(content_index):
                    yield 'event: content_block_stop\n'
                    yield f'data: {{"type":"content_block_stop", "index":{i}}}\n\n'

                claude_stop_reason = "end_turn" if stop_reason == "stop" else "tool_use" if stop_reason == "tool_calls" else stop_reason or "end_turn"
                yield 'event: message_delta\n'
                yield f'data: {{"type":"message_delta", "delta":{{"stop_reason":"{claude_stop_reason}", "stop_sequence":null}}, "usage":{{"output_tokens":{full_output_tokens}}}}}\n\n'

                yield 'event: message_stop\n'
                yield 'data: {"type":"message_stop"}\n\n'

            return Response(transform_stream(openai_response), content_type='text/event-stream')
        else:
            choice = openai_response["choices"][0]
            message = choice["message"]
            claude_content = []
            if "content" in message and message["content"]:
                claude_content.append({"type": "text", "text": message["content"]})
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    fn = tc["function"]
                    input_dict = json.loads(fn["arguments"])
                    claude_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": fn["name"],
                        "input": input_dict
                    })
            stop_reason = "end_turn" if choice["finish_reason"] == "stop" else "tool_use" if choice["finish_reason"] == "tool_calls" else choice["finish_reason"]
            claude_resp = {
                "id": openai_response.get("id", "msg_1"),
                "type": "message",
                "role": "assistant",
                "model": openai_response["model"],
                "content": claude_content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": openai_response.get("usage", {"input_tokens": 0, "output_tokens": 0})
            }
            return jsonify(claude_resp)
    except Exception as e:
        return jsonify({
            "type": "error",
            "error": {
                "type": "server_error",
                "message": str(e)
            }
        }), 500


if __name__ == '__main__':
    print(load_adapter(core, 'ustc'))
    if len(sys.argv) > 0:
        try:
            port = int(sys.argv[1])
        except Exception as e:
            port = 5000
    app.run(host='0.0.0.0', port=port, debug=True)