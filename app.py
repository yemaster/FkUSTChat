from flask import Flask, request, jsonify, render_template, Response

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


if __name__ == '__main__':
    print(load_adapter(core, 'ustc'))
    app.run(host='0.0.0.0', debug=True)