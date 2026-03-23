# === Jarvis 4.0 STT Server — Whisper Base Model ===
# Handles transcription requests from the router or wake word listener

import whisper
import tempfile
import os
import sounddevice as sd
import soundfile as sf
import numpy as np

# Load Whisper base model once at startup
print("[STT] Loading Whisper base model...")
MODEL = whisper.load_model("small")
print("[STT] Whisper base model loaded.")

# Recording settings
SAMPLE_RATE = 16000
CHANNELS = 1


def record_audio(duration: int = 5) -> str:
    """
    Record audio from the microphone for a given duration.
    Returns the path to the saved temp wav file.
    """
    print(f"[STT] Recording for {duration} seconds...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32"
    )
    sd.wait()
    print("[STT] Recording complete.")

    # Save to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE)
    return tmp.name


def transcribe_file(filepath: str) -> str:
    """
    Transcribe an audio file using Whisper.
    Returns the transcribed text.
    """
    try:
        print(f"[STT] Transcribing: {filepath}")
        result = MODEL.transcribe(filepath, fp16=False)
        text = result["text"].strip()
        print(f"[STT] Transcription: {text}")
        return text
    except Exception as e:
        print(f"[STT] Transcription error: {e}")
        return ""
    finally:
        # Clean up temp file
        try:
            os.remove(filepath)
        except Exception:
            pass


def record_and_transcribe(duration: int = 5) -> str:
    """
    Record audio then transcribe it.
    Returns transcribed text.
    """
    filepath = record_audio(duration)
    return transcribe_file(filepath)


def handle(user_input: str) -> dict:
    """
    MCP organ interface.
    Called by mcp_router_hub when intent is 'stt'.
    """
    try:
        # Parse duration from input if provided
        # e.g. "transcribe 8" means record for 8 seconds
        duration = 5
        parts = user_input.lower().replace("transcribe", "").strip()
        if parts.isdigit():
            duration = int(parts)

        text = record_and_transcribe(duration)

        if not text:
            return {"data": "Sorry, I could not understand the audio."}

        return {"data": text, "transcription": text}

    except Exception as e:
        return {"data": f"[STT Error] {str(e)}"}