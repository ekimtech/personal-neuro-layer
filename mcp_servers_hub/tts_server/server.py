import json
import sys
import subprocess
import os
from pathlib import Path

# ---------------------------------------------------------
# 1. Resolve Piper paths
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PIPER_DIR = BASE_DIR / ".." / ".." / "tools" / "piper"
PIPER_EXE = PIPER_DIR / "piper.exe"
VOICES_DIR = PIPER_DIR / "voices"

# ---------------------------------------------------------
# 2. Tool definitions
# ---------------------------------------------------------
TOOLS = {
    "tts": {
        "name": "tts",
        "description": "Generate speech audio using Piper TTS",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to convert to speech"},
                "voice": {"type": "string", "description": "Voice model name (without .onnx)"}
            },
            "required": ["text"]
        }
    }
}

# ---------------------------------------------------------
# 3. Send a JSON-RPC response
# ---------------------------------------------------------
def send(obj):
    print(json.dumps(obj), flush=True)

# ---------------------------------------------------------
# 4. Handle initialize — respond with capabilities
# ---------------------------------------------------------
def handle_initialize(req_id):
    send({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "tts",
                "version": "1.0.0"
            },
            "capabilities": {
                "tools": {}   # <-- OBJECT, not array. Tool list comes via tools/list
            }
        }
    })

# ---------------------------------------------------------
# 5. Handle tools/list — return the tool definitions
# ---------------------------------------------------------
def handle_tools_list(req_id):
    send({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": list(TOOLS.values())   # array here is correct for tools/list
        }
    })

# ---------------------------------------------------------
# 6. Run Piper
# ---------------------------------------------------------
def run_piper(text, voice):
    model_path = VOICES_DIR / f"{voice}.onnx"

    # Save directly into the Flask static folder
    output_path = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "static", "output.wav"))

    cmd = [
        str(PIPER_EXE),
        "--model", str(model_path),
        "--output_file", output_path,
        "--length_scale", "0.85"   # <‑‑ speed up voice
    ]

    # Piper reads text from stdin, not a --text flag
    result = subprocess.run(
        cmd,
        input=text,
        text=True,
        capture_output=True,
        check=True
    )
    return {"audio_path": output_path}

# ---------------------------------------------------------
# 7. Handle tools/call
# ---------------------------------------------------------
def handle_tools_call(req_id, params):
    tool_name = params.get("name", "")
    args = params.get("arguments", {})

    if tool_name == "tts":
        text = args.get("text", "")
        voice = "en_GB-alan-medium"
        # Validate voice exists, fall back to default if not
        if not (VOICES_DIR / f"{voice}.onnx").exists() or not (VOICES_DIR / f"{voice}.onnx.json").exists():
            voice = "en_GB-alan-medium"
        result = run_piper(text, voice)
        send({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": str(result)}]
            }
        })
    else:
        send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
        })

# ---------------------------------------------------------
# 8. MCP main loop
# ---------------------------------------------------------
def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except Exception:
            continue

        if "jsonrpc" not in request:
            continue

        method = request.get("method", "")
        req_id = request.get("id", None)
        params = request.get("params", {})

        if method == "initialize":
            handle_initialize(req_id)

        elif method == "notifications/initialized":
            pass  # No response needed for notifications

        elif method == "tools/list":
            handle_tools_list(req_id)

        elif method == "tools/call":
            handle_tools_call(req_id, params)

        elif req_id is not None:
            # Unknown method with an ID — send a method-not-found error
            send({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

def handle(user_input: str) -> dict:
    # Strip "speak " or "say " from the input
    cleaned = user_input.replace("speak ", "", 1).replace("say ", "", 1).strip()

    # Default voice
    voice = "en_GB-alan-medium"

    # Run Piper
    result = run_piper(cleaned, voice)

    return {"data": f"Audio generated at {result['audio_path']}"}

if __name__ == "__main__":
    main()