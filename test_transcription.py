#!/usr/bin/env python3
"""
Test script for whisper transcription accuracy.
Press SPACE to start recording, release to transcribe and print result.
"""

import os
import sys
import time
import wave
import tempfile
import subprocess
import multiprocessing
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import numpy as np
import sounddevice as sd
from pynput import keyboard

# Settings from .env
WHISPER_CPP_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_CPP_PATH",
    "~/whisper.cpp/build/bin/whisper-cli"
))
WHISPER_MODEL_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_MODEL_PATH",
    "~/whisper.cpp/models/ggml-large-v3-turbo.bin"
))
INPUT_DEVICE = os.environ.get("INPUT_DEVICE", None)
SAMPLE_RATE = 16000
CHANNELS = 1

# Recording state
frames = []
recording = False


def log(msg):
    print(msg, flush=True)


def transcribe_with_params(audio_bytes: bytes, params: dict) -> str:
    """Transcribe using local whisper.cpp with custom parameters."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        cmd = [WHISPER_CPP_PATH, "-m", WHISPER_MODEL_PATH, "-f", temp_path]

        # Add custom parameters
        for key, value in params.items():
            if value is True:
                cmd.append(f"--{key}")
            elif value is not False and value is not None:
                cmd.extend([f"--{key}", str(value)])

        log(f"\n🔧 Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    finally:
        os.unlink(temp_path)


class TestRecorder:
    def __init__(self):
        self.frames = []
        self.recording = False
        self.stream = None

    def callback(self, indata, frame_count, time_info, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start(self):
        log("🎤 Recording... (release SPACE to stop)")
        self.frames = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.int16,
            device=INPUT_DEVICE,
            callback=self.callback
        )
        self.stream.start()

    def stop(self) -> bytes:
        log("⏹️  Stopped")
        self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.frames:
            return b""

        # Convert to WAV
        import io
        audio_data = np.concatenate(self.frames, axis=0)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        return buffer.getvalue()


def main():
    log("=" * 60)
    log("Whisper Transcription Test")
    log("=" * 60)
    log(f"Model: {WHISPER_MODEL_PATH}")
    log(f"Device: {INPUT_DEVICE or 'System Default'}")
    log("")
    log("Press and HOLD SPACE to record, release to transcribe")
    log("Press Q to quit")
    log("=" * 60)
    log("")

    recorder = TestRecorder()
    space_pressed = False

    def on_press(key):
        nonlocal space_pressed

        if key == keyboard.Key.space and not space_pressed:
            space_pressed = True
            recorder.start()
        elif hasattr(key, 'char') and key.char == 'q':
            log("\n👋 Goodbye!")
            return False

    def on_release(key):
        nonlocal space_pressed

        if key == keyboard.Key.space and space_pressed:
            space_pressed = False
            audio_bytes = recorder.stop()

            if not audio_bytes:
                log("⚠️  No audio recorded")
                return

            log(f"📝 Transcribing {len(audio_bytes)} bytes...\n")

            # Test with different parameter sets
            param_sets = [
                {
                    "name": "Current (default)",
                    "params": {"no-timestamps": True, "nt": True}
                },
                {
                    "name": "Best Quality",
                    "params": {"no-timestamps": True, "best-of": 5, "beam-size": 5, "language": "en"}
                },
                {
                    "name": "High Temperature (more creative)",
                    "params": {"no-timestamps": True, "temperature": 0.8, "language": "en"}
                },
                {
                    "name": "Low Temperature (more conservative)",
                    "params": {"no-timestamps": True, "temperature": 0.0, "language": "en"}
                }
            ]

            for i, param_set in enumerate(param_sets, 1):
                log(f"\n{'='*60}")
                log(f"Test {i}/{len(param_sets)}: {param_set['name']}")
                log(f"{'='*60}")
                result = transcribe_with_params(audio_bytes, param_set["params"])
                log(f"\n📋 Result:")
                log(f">>> {result}")
                log("")

            log("\n✅ Ready for next recording (press SPACE)")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
