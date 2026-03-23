# === Script Runner Organ — script_runner_server.py ===
# Executes arbitrary Python scripts pasted into Jarvis chat.
# Captures stdout/stderr and returns output.
# Built: 03-21-26

import os
import sys
import uuid
import subprocess
import logging

logger = logging.getLogger("script_runner")

_HERE    = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(_HERE))
SCRIPTS_DIR = os.path.join(BASE_DIR, "temp_scripts")


def _extract_code(user_input: str) -> str:
    """
    Extract Python code from user input.
    Handles raw paste, markdown code blocks, and 'run this: <code>' format.
    """
    text = user_input.strip()

    # Strip markdown code fences
    if "```python" in text:
        text = text.split("```python", 1)[1]
        text = text.split("```")[0].strip()
        return text
    if "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```")[0].strip()
        return text

    # Strip trigger prefix like "run this:" or "execute this:"
    for prefix in ["run this:", "execute this:", "run script:", "run:"]:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            return text

    # Raw code paste — return as-is
    return text


def run_script(user_input: str, timeout: int = 15) -> dict:
    """Save code to temp file, execute it, return output."""
    code = _extract_code(user_input)

    if not code:
        return {"success": False, "output": "No code found to run."}

    # Create temp scripts folder if needed
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    script_id   = uuid.uuid4().hex[:8]
    script_path = os.path.join(SCRIPTS_DIR, f"script_{script_id}.py")

    try:
        # Write code to temp file
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info(f"[ScriptRunner] Running script_{script_id}.py")

        # Execute using the current Python interpreter (inside venv)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=BASE_DIR
        )

        output  = result.stdout.strip()
        errors  = result.stderr.strip()

        if result.returncode != 0 and errors:
            logger.warning(f"[ScriptRunner] Script error: {errors[:200]}")
            return {
                "success": False,
                "output": f"Script error:\n{errors}"
            }

        if not output and not errors:
            return {"success": True, "output": "Script ran successfully with no output."}

        response = output
        if errors:
            response += f"\n\nWarnings:\n{errors}"

        return {"success": True, "output": response}

    except subprocess.TimeoutExpired:
        logger.warning(f"[ScriptRunner] Script_{script_id} timed out after {timeout}s")
        return {
            "success": False,
            "output": (
                f"Script timed out after {timeout} seconds. "
                "This usually means the script is waiting for input() which "
                "can't work through the web interface. "
                "For interactive games say 'start number game' instead."
            )
        }
    except Exception as e:
        logger.error(f"[ScriptRunner] Unexpected error: {e}")
        return {"success": False, "output": f"Could not run script: {e}"}
    finally:
        # Always clean up temp file
        try:
            os.remove(script_path)
        except Exception:
            pass


def is_code_paste(user_input: str) -> bool:
    """
    Detect if user pasted raw Python code (multiline, looks like Python).
    Used by router to auto-route to script runner.
    """
    lines = user_input.strip().splitlines()
    if len(lines) < 4:
        return False
    code_signals = ("import ", "def ", "class ", "for ", "while ",
                    "if __name__", "print(", "return ", "try:", "except")
    matches = sum(1 for line in lines if line.strip().startswith(code_signals))
    return matches >= 2


# ---------------------------------------------------------
# Handle — MCP organ interface
# ---------------------------------------------------------
def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # List temp scripts (shouldn't exist but useful for debug)
    if any(k in text for k in ["list scripts", "show scripts"]):
        if os.path.exists(SCRIPTS_DIR):
            files = os.listdir(SCRIPTS_DIR)
            if files:
                return {"data": f"Temp scripts: {', '.join(files)}"}
        return {"data": "No temp scripts found."}

    # Run the script
    result = run_script(user_input)
    if result["success"]:
        output = result["output"]
        # Truncate very long output
        if len(output) > 1500:
            output = output[:1500] + "\n... (output truncated)"
        return {"data": f"Script output:\n{output}"}
    else:
        return {"data": result["output"]}
