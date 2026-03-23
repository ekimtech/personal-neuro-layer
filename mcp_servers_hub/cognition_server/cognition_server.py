# === Cognition Organ Wrapper ===
# Connects the new modular router to your existing cognition engine.

from model_injection.cognition import generate_response

def handle(user_input: str, session=None) -> dict:
    """
    Wraps your existing cognition engine (generate_response)
    into the new organ interface.
    """
    try:
        result = generate_response(user_input, session=session)
        reply = result.get("message", "")

        return {
            "message": reply
        }

    except Exception as e:
        return {
            "message": f"[Cognition Error] {str(e)}"
        }

