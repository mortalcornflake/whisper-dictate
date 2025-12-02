#!/usr/bin/env python3
"""
Whisper Dictate - Simple global dictation tool using Whisper.
Hold the hotkey, speak, release to transcribe and paste.
"""

import io
import os
import sys
from dotenv import load_dotenv

# Load .env file from script directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import wave
import tempfile
import threading
import subprocess
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyperclip
import requests
from pynput import keyboard

# Force unbuffered output
def log(msg):
    print(msg, flush=True)

# === Configuration ===
# Using Right Option key alone for simplicity
HOTKEY_KEY = keyboard.Key.alt_r  # Right Option key
RESET_COMBO = {keyboard.Key.ctrl, keyboard.Key.shift}  # Ctrl+Shift for reset combo
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1

# Audio input device - set to None for system default, or device name/index
# Examples: "MacBook Pro Microphone", "iMac Microphone", "USB Microphone"
# Tip: Use a specific mic name to dictate through built-in mic while using AirPods for audio
INPUT_DEVICE = os.environ.get("INPUT_DEVICE", None)  # None = system default

# Transcription backend: "groq", "openai", or "local"
BACKEND = os.environ.get("DICTATE_BACKEND", "groq")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Local whisper.cpp fallback settings
# Set these env vars or update defaults to your whisper.cpp installation
WHISPER_CPP_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_CPP_PATH",
    "~/whisper.cpp/build/bin/whisper-cli"
))
WHISPER_MODEL_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_MODEL_PATH",
    "~/whisper.cpp/models/ggml-base.en.bin"
))
FALLBACK_TO_LOCAL = True  # Fall back to local whisper.cpp if cloud fails


def notify(title, message):
    """Show macOS notification."""
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ], capture_output=True)


def sound(name="Pop"):
    """Play system sound."""
    subprocess.run(["afplay", f"/System/Library/Sounds/{name}.aiff"], capture_output=True)


class Recorder:
    def __init__(self):
        self.frames = []
        self.recording = False
        self.stream = None

    def start(self):
        self.frames = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.int16,
            device=INPUT_DEVICE,
            callback=self._callback
        )
        self.stream.start()
        log("🎤 Recording...")
        sound("Pop")

    def _callback(self, indata, frame_count, time_info, status):
        if self.recording:
            self.frames.append(indata.copy())

    def stop(self) -> bytes:
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        log("⏹️  Stopped recording")
        sound("Blow")

        if not self.frames:
            return b""

        audio_data = np.concatenate(self.frames, axis=0)

        # Convert to WAV bytes
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        return buffer.getvalue()


def transcribe_groq(audio_bytes: bytes) -> str:
    """Transcribe using Groq API (fast, cheap). Raises on network error."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={"model": "whisper-large-v3"},
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(f"Groq API error: {response.status_code}")

    return response.json().get("text", "")


def transcribe_openai(audio_bytes: bytes) -> str:
    """Transcribe using OpenAI Whisper API."""
    if not OPENAI_API_KEY:
        log("❌ OPENAI_API_KEY not set")
        return ""

    response = requests.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={"model": "whisper-1"}
    )

    if response.status_code != 200:
        log(f"❌ OpenAI API error: {response.text}")
        return ""

    return response.json().get("text", "")


def transcribe_local(audio_bytes: bytes) -> str:
    """Transcribe using local whisper.cpp."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        cmd = [WHISPER_CPP_PATH]
        if WHISPER_MODEL_PATH:
            cmd.extend(["-m", WHISPER_MODEL_PATH])
        cmd.extend(["-f", temp_path, "--no-timestamps", "-nt"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    finally:
        os.unlink(temp_path)


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio using configured backend, with local fallback."""
    log(f"📝 Transcribing with {BACKEND}...")

    try:
        if BACKEND == "groq":
            return transcribe_groq(audio_bytes)
        elif BACKEND == "openai":
            return transcribe_openai(audio_bytes)
        elif BACKEND == "local":
            return transcribe_local(audio_bytes)
        else:
            log(f"❌ Unknown backend: {BACKEND}")
            return ""
    except (requests.exceptions.RequestException, RuntimeError, ValueError) as e:
        if FALLBACK_TO_LOCAL and BACKEND != "local":
            log(f"⚠️  Cloud failed ({e}), falling back to local whisper.cpp...")
            notify("Whisper Dictate", f"Using local fallback: {e}")
            return transcribe_local(audio_bytes)
        else:
            log(f"❌ Transcription failed: {e}")
            notify("Whisper Dictate", f"Transcription failed: {e}")
            return ""


def get_clipboard() -> str:
    """Get current clipboard contents using pbpaste."""
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout


def set_clipboard(text: str):
    """Set clipboard contents using pbcopy."""
    subprocess.run(['pbcopy'], input=text.encode(), check=True)


def paste_text(text: str):
    """Copy text to clipboard, paste it, and restore previous clipboard contents."""
    import time

    # Save current clipboard
    old_clipboard = get_clipboard()
    log(f"📋 Saved clipboard: {old_clipboard[:50]}{'...' if len(old_clipboard) > 50 else ''}")

    # Copy new text and paste
    pyperclip.copy(text)

    # Use osascript to paste (more reliable than pyautogui on macOS)
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to keystroke "v" using command down'
    ])
    log(f"✅ Pasted: {text[:50]}{'...' if len(text) > 50 else ''}")

    # Wait for paste to complete before restoring clipboard
    time.sleep(0.5)

    # Restore original clipboard after paste completes
    set_clipboard(old_clipboard)
    log(f"♻️  Restored clipboard: {old_clipboard[:50]}{'...' if len(old_clipboard) > 50 else ''}")

    # Play sound AFTER clipboard is restored, so user knows it's safe to paste
    sound("Glass")


class DictationListener:
    def __init__(self):
        self.recorder = Recorder()
        self.is_recording = False
        self.pressed_keys = set()

    def on_press(self, key):
        self.pressed_keys.add(key)

        # Check for reset combo: Ctrl+Shift+R
        if (RESET_COMBO.issubset(self.pressed_keys) and
            (key == keyboard.KeyCode.from_char('r') or key == keyboard.KeyCode.from_char('R'))):
            self.reset()
            return

        if key == HOTKEY_KEY and not self.is_recording:
            self.is_recording = True
            self.recorder.start()

    def on_release(self, key):
        self.pressed_keys.discard(key)

        if self.is_recording and key == HOTKEY_KEY:
            self.is_recording = False
            audio_bytes = self.recorder.stop()

            if audio_bytes:
                # Process in background thread so we don't block the listener
                threading.Thread(
                    target=self._process_audio,
                    args=(audio_bytes,),
                    daemon=True
                ).start()

    def _process_audio(self, audio_bytes: bytes):
        text = transcribe(audio_bytes)
        if text:
            paste_text(text)

    def reset(self):
        """Reset recorder if stuck - triggered by Ctrl+Shift+R."""
        log("⚙️  Reset triggered (Ctrl+Shift+R)")
        self.is_recording = False
        if self.recorder.stream:
            try:
                self.recorder.stream.stop()
                self.recorder.stream.close()
            except:
                pass
        self.recorder = Recorder()
        notify("Whisper Dictate", "Recorder reset - ready to record")
        sound("Glass")
        log("✅ Recorder reset complete")

    def run(self):
        log("=" * 50)
        log("Whisper Dictate")
        log("=" * 50)
        log(f"Backend: {BACKEND}")
        if FALLBACK_TO_LOCAL:
            log(f"Fallback: local whisper.cpp")
        log(f"Hotkey: Right Option key (hold to record)")
        log(f"Reset: Ctrl+Shift+R (if stuck recording)")
        log("Press Ctrl+C to quit")
        log("=" * 50)

        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            listener.join()


def main():
    # Check for required API keys based on backend
    if BACKEND == "groq" and not GROQ_API_KEY:
        if FALLBACK_TO_LOCAL:
            log("⚠️  GROQ_API_KEY not set - will use local whisper.cpp only")
        else:
            log("⚠️  GROQ_API_KEY not set. Get one at https://console.groq.com")
            sys.exit(1)
    elif BACKEND == "openai" and not OPENAI_API_KEY:
        if FALLBACK_TO_LOCAL:
            log("⚠️  OPENAI_API_KEY not set - will use local whisper.cpp only")
        else:
            log("⚠️  OPENAI_API_KEY not set.")
            sys.exit(1)

    # Verify local whisper.cpp exists if we might need it
    if FALLBACK_TO_LOCAL or BACKEND == "local":
        if not os.path.exists(WHISPER_CPP_PATH):
            log(f"❌ whisper.cpp not found at: {WHISPER_CPP_PATH}")
            sys.exit(1)
        if not os.path.exists(WHISPER_MODEL_PATH):
            log(f"❌ Whisper model not found at: {WHISPER_MODEL_PATH}")
            sys.exit(1)

    listener = DictationListener()
    try:
        listener.run()
    except KeyboardInterrupt:
        log("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
