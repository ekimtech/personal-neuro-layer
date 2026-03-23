# === Jarvis 4.0 Wake Word Listener — with Status Updates ===

import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import os
import whisper
import requests

# --- Config ---
WAKE_WORD = "jarvis"
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 5
COMMAND_SECONDS = 10
JARVIS_TALK_URL = "http://127.0.0.1:5000/talk"
WAKE_SESSION_ID = 1

print("[WakeWord] Loading Whisper small model...")
_model = whisper.load_model("small")
print("[WakeWord] Whisper ready.")

_running = False
_thread = None
_triggered = False


def _set_status(status: str):
    """Update status in jarvis_routes for WebUI display."""
    try:
        from jarvis_routes import set_stt_status
        set_stt_status(status)
    except Exception:
        pass


def _save_and_transcribe(audio: np.ndarray) -> str:
    """Save numpy audio to temp file and transcribe with Whisper."""
    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        sf.write(tmp_path, audio, SAMPLE_RATE)
        result = _model.transcribe(tmp_path, fp16=False, language="en")
        text = result["text"].strip().lower()
        return text
    except Exception as e:
        print(f"[WakeWord] Transcription error: {e}")
        return ""
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _record(seconds: int) -> np.ndarray:
    """Record audio for given seconds and return numpy array."""
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32"
    )
    sd.wait()
    return audio


def _send_to_jarvis(text: str):
    """Send transcribed command to Jarvis /talk endpoint."""
    try:
        _set_status("processing")
        print(f"[WakeWord] Sending to Jarvis: {text}")
        response = requests.post(
            JARVIS_TALK_URL,
            json={"message": text, "session_id": WAKE_SESSION_ID},
            timeout=300
        )
        data = response.json()
        reply = data.get("message", "")
        print(f"[WakeWord] Jarvis replied: {reply}")

        # Push reply to WebUI queue
        from jarvis_routes import push_wake_message
        push_wake_message(reply)

        # Update status to speaking then back to listening
        _set_status("speaking")
        time.sleep(3)
        _set_status("listening")

    except Exception as e:
        print(f"[WakeWord] Failed to send to Jarvis: {e}")
        _set_status("listening")


def _listen_loop():
    """Main wake word listening loop."""
    global _running, _triggered

    print(f"[WakeWord] Listening for: '{WAKE_WORD}'")
    _set_status("listening")

    while _running:
        try:
            # Record a detection chunk
            audio_chunk = _record(CHUNK_SECONDS)
            text = _save_and_transcribe(audio_chunk)

            if not text:
                continue

            print(f"[WakeWord] Heard: {text}")

            if WAKE_WORD in text and not _triggered:
                _triggered = True
                _set_status("wake_detected")
                print("[WakeWord] Wake word detected!")

                # Check if command already in same chunk
                after_wake = text.split(WAKE_WORD, 1)[-1].strip(" .,!?")

                if len(after_wake.split()) >= 2:
                    print(f"[WakeWord] Command in same chunk: {after_wake}")
                    _send_to_jarvis(after_wake)
                    _triggered = False
                    continue

                # Record fresh command chunk
                _set_status("recording")
                print(f"[WakeWord] Recording command for {COMMAND_SECONDS} seconds...")
                command_audio = _record(COMMAND_SECONDS)
                command_text = _save_and_transcribe(command_audio)
                command_text = command_text.replace(WAKE_WORD, "").strip(" .,!?")

                print(f"[WakeWord] Command: {command_text}")

                if command_text and len(command_text.split()) >= 1:
                    _send_to_jarvis(command_text)
                else:
                    print("[WakeWord] No command detected, resuming.")
                    _set_status("listening")

                _triggered = False

        except Exception as e:
            print(f"[WakeWord] Loop error: {e}")
            _triggered = False
            _set_status("listening")
            time.sleep(1)


def start():
    """Start the wake word listener in a background thread."""
    global _running, _thread
    if _running:
        print("[WakeWord] Already running.")
        return
    _running = True
    _thread = threading.Thread(target=_listen_loop, daemon=True)
    _thread.start()
    print("[WakeWord] Listener started in background.")


def stop():
    """Stop the wake word listener."""
    global _running
    _running = False
    print("[WakeWord] Listener stopped.")