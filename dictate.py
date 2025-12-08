#!/usr/bin/env python3
"""
Whisper Dictate - Simple global dictation tool using Whisper.
Hold the hotkey, speak, release to transcribe and paste.
"""

import io
import os
import sys
import time
import wave
import tempfile
import threading
import subprocess
import multiprocessing
import signal
from pathlib import Path

# Suppress urllib3 SSL warning (cosmetic, caused by system Python's LibreSSL)
import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

from dotenv import load_dotenv

# Load .env file from script directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import numpy as np
import sounddevice as sd
import pyperclip
import requests
from pynput import keyboard

# Force unbuffered output
def log(msg):
    print(msg, flush=True)


def parse_hotkey(key_str):
    """Parse hotkey string from .env to pynput Key object."""
    key_map = {
        'alt_r': keyboard.Key.alt_r,
        'alt_l': keyboard.Key.alt_l,
        'option_r': keyboard.Key.alt_r,  # macOS alias
        'option_l': keyboard.Key.alt_l,  # macOS alias
        'ctrl_r': keyboard.Key.ctrl_r,
        'ctrl_l': keyboard.Key.ctrl_l,
        'cmd_r': keyboard.Key.cmd_r,
        'cmd_l': keyboard.Key.cmd_l,
        'shift_r': keyboard.Key.shift_r,
        'shift_l': keyboard.Key.shift_l,
        'f5': keyboard.Key.f5,
        'f6': keyboard.Key.f6,
        'f7': keyboard.Key.f7,
        'f8': keyboard.Key.f8,
        'f9': keyboard.Key.f9,
        'f10': keyboard.Key.f10,
    }
    return key_map.get(key_str.lower(), keyboard.Key.alt_r)


def get_hotkey_name(key):
    """Get friendly name for hotkey."""
    name_map = {
        keyboard.Key.alt_r: "Right Option",
        keyboard.Key.alt_l: "Left Option",
        keyboard.Key.ctrl_r: "Right Control",
        keyboard.Key.ctrl_l: "Left Control",
        keyboard.Key.cmd_r: "Right Command",
        keyboard.Key.cmd_l: "Left Command",
        keyboard.Key.shift_r: "Right Shift",
        keyboard.Key.shift_l: "Left Shift",
        keyboard.Key.f5: "F5",
        keyboard.Key.f6: "F6",
        keyboard.Key.f7: "F7",
        keyboard.Key.f8: "F8",
        keyboard.Key.f9: "F9",
        keyboard.Key.f10: "F10",
    }
    return name_map.get(key, str(key))


# === Configuration ===
HOTKEY_KEY = parse_hotkey(os.environ.get("HOTKEY", "alt_r"))
RESET_COMBO = {keyboard.Key.ctrl, keyboard.Key.shift}  # Ctrl+Shift for reset combo
PRESERVE_CLIPBOARD = os.environ.get("PRESERVE_CLIPBOARD", "true").lower() in ("true", "1", "yes")
AUTO_PRESS_ENTER = os.environ.get("AUTO_PRESS_ENTER", "false").lower() in ("true", "1", "yes")
AUTO_STOP_TIMEOUT = int(os.environ.get("AUTO_STOP_TIMEOUT", "45"))  # Seconds before auto-stop stuck recordings
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
WHISPER_SERVER_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_SERVER_PATH",
    "~/whisper.cpp/build/bin/whisper-server"
))
WHISPER_MODEL_PATH = os.path.expanduser(os.environ.get(
    "WHISPER_MODEL_PATH",
    "~/whisper.cpp/models/ggml-base.en.bin"
))
FALLBACK_TO_LOCAL = True  # Fall back to local whisper.cpp if cloud fails
WHISPER_SERVER_PORT = 8080  # Port for whisper server
WHISPER_SERVER_IDLE_TIMEOUT = 1800  # Shutdown server after 30 min idle (seconds)

# Global server state (lazy initialization)
_whisper_server_process = None
_whisper_server_last_used = None
_whisper_server_lock = threading.Lock()


def notify(title, message):
    """Show macOS notification."""
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ], capture_output=True)


def sound(name="Pop"):
    """Play system sound."""
    subprocess.run(["afplay", f"/System/Library/Sounds/{name}.aiff"], capture_output=True)


def recording_worker(output_path, device_name, sample_rate, channels):
    """
    Worker function that runs in a subprocess to record audio.
    Writes raw audio frames to a file continuously until killed.
    """
    import numpy as np
    import sounddevice as sd
    import signal
    import sys

    frames = []
    recording = True
    should_exit = False

    def callback(indata, frame_count, time_info, status):
        if recording:
            frames.append(indata.copy())

    def signal_handler(signum, frame):
        # Handle termination signal - save and exit
        nonlocal should_exit, recording
        recording = False
        should_exit = True

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start recording
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype=np.int16,
        device=device_name,
        callback=callback
    )
    stream.start()

    try:
        # Record until signaled to stop
        while not should_exit:
            time.sleep(0.1)
    finally:
        # Save what we recorded before exiting
        recording = False
        try:
            stream.stop()
            stream.close()
        except:
            pass

        # ALWAYS save frames, even if stream fails
        if frames:
            try:
                audio_data = np.concatenate(frames, axis=0)
                # Save as raw numpy array
                np.save(output_path, audio_data)
                sys.stdout.flush()  # Ensure writes complete
            except Exception as e:
                # Log to stderr which parent can see
                print(f"Error saving audio: {e}", file=sys.stderr)
                sys.stderr.flush()


class Recorder:
    """Subprocess-based recorder that can be forcefully killed."""

    def __init__(self):
        self.process = None
        self.temp_file = None
        self.start_time = None

    def start(self):
        # Create temp file for this recording
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.npy', delete=False)
        self.temp_file.close()

        self.start_time = time.time()

        # Spawn subprocess to handle recording
        self.process = multiprocessing.Process(
            target=recording_worker,
            args=(self.temp_file.name, INPUT_DEVICE, SAMPLE_RATE, CHANNELS)
        )
        self.process.start()

        log("🎤 Recording...")
        sound("Pop")

    def stop(self) -> bytes:
        """Stop recording subprocess and extract audio."""
        duration = 0
        if self.start_time:
            duration = time.time() - self.start_time

        log(f"⏹️  Stopping recording subprocess (duration: {duration:.1f}s)")

        # Kill the subprocess
        if self.process and self.process.is_alive():
            log("🔫 Terminating recording subprocess...")
            self.process.terminate()  # Send SIGTERM - subprocess will save and exit
            self.process.join(timeout=5)  # Wait up to 5 seconds for clean shutdown

            if self.process.is_alive():
                log("💀 Force killing stuck subprocess...")
                self.process.kill()  # SIGKILL - nuclear option
                self.process.join(timeout=2)

        # Give subprocess a moment to finish writing file
        time.sleep(0.1)

        # Read the recorded audio from temp file
        audio_bytes = b""
        try:
            if os.path.exists(self.temp_file.name):
                audio_data = np.load(self.temp_file.name)

                if len(audio_data) > 0:
                    # Convert to WAV bytes
                    buffer = io.BytesIO()
                    with wave.open(buffer, "wb") as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(2)  # 16-bit
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(audio_data.tobytes())

                    audio_bytes = buffer.getvalue()
                    log(f"✅ Extracted {len(audio_bytes)} bytes from subprocess")
        except Exception as e:
            log(f"⚠️  Error reading recorded audio: {e}")
        finally:
            # Cleanup temp file
            try:
                if self.temp_file and os.path.exists(self.temp_file.name):
                    os.unlink(self.temp_file.name)
            except:
                pass

        return audio_bytes


def transcribe_groq(audio_bytes: bytes) -> str:
    """Transcribe using Groq API (fast, cheap). Raises on network error."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={"model": "whisper-large-v3"},  # Use full v3 on Groq's LPUs for max accuracy
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


def start_whisper_server():
    """Start whisper server in background (lazy initialization)."""
    global _whisper_server_process, _whisper_server_last_used

    with _whisper_server_lock:
        # Check if already running
        if _whisper_server_process and _whisper_server_process.poll() is None:
            _whisper_server_last_used = time.time()
            return

        # Check if server binary exists
        if not os.path.exists(WHISPER_SERVER_PATH):
            log(f"⚠️  whisper-server not found at {WHISPER_SERVER_PATH} - using CLI mode")
            return

        log(f"🚀 Starting whisper server (model will load, ~5-10sec)...")

        # Start server process
        cmd = [
            WHISPER_SERVER_PATH,
            "-m", WHISPER_MODEL_PATH,
            "--port", str(WHISPER_SERVER_PORT),
            "--host", "127.0.0.1"
        ]

        _whisper_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for server to be ready (check if port is listening)
        max_wait = 30  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            # Check if process died during startup
            if _whisper_server_process.poll() is not None:
                log("⚠️  Whisper server process died during startup - falling back to CLI mode")
                _whisper_server_process = None
                return

            try:
                response = requests.get(f"http://127.0.0.1:{WHISPER_SERVER_PORT}/", timeout=1)
                if response.status_code in (200, 404):  # Server is up
                    _whisper_server_last_used = time.time()
                    log(f"✅ Whisper server ready (PID: {_whisper_server_process.pid})")
                    return
            except requests.exceptions.RequestException:
                time.sleep(0.5)

        # Timeout - kill the stuck process and clean up
        log("⚠️  Whisper server startup timeout - killing process and falling back to CLI mode")
        try:
            _whisper_server_process.kill()
            _whisper_server_process.wait(timeout=2)
        except:
            pass
        _whisper_server_process = None


def stop_whisper_server():
    """Stop the whisper server if running."""
    global _whisper_server_process

    with _whisper_server_lock:
        if _whisper_server_process and _whisper_server_process.poll() is None:
            log(f"🛑 Stopping whisper server (PID: {_whisper_server_process.pid})")
            _whisper_server_process.terminate()
            try:
                _whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log("⚠️  Server didn't stop gracefully, force killing...")
                _whisper_server_process.kill()
                _whisper_server_process.wait(timeout=2)
        _whisper_server_process = None


def check_server_idle():
    """Background thread to shutdown idle server."""
    global _whisper_server_last_used

    while True:
        time.sleep(60)  # Check every minute

        # Use lock to safely read server state
        with _whisper_server_lock:
            if _whisper_server_process and _whisper_server_last_used:
                idle_time = time.time() - _whisper_server_last_used
                if idle_time > WHISPER_SERVER_IDLE_TIMEOUT:
                    log(f"💤 Whisper server idle for {int(idle_time/60)}min - shutting down")

        # Call stop outside the lock to avoid deadlock
        if _whisper_server_process and _whisper_server_last_used:
            idle_time = time.time() - _whisper_server_last_used
            if idle_time > WHISPER_SERVER_IDLE_TIMEOUT:
                stop_whisper_server()


def transcribe_local(audio_bytes: bytes) -> str:
    """Transcribe using local whisper.cpp (server mode with fallback to CLI)."""
    global _whisper_server_last_used, _whisper_server_process

    # Try server mode first (if available)
    if _whisper_server_process and _whisper_server_process.poll() is None:
        try:
            _whisper_server_last_used = time.time()

            # Send audio to server
            files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
            data = {
                "temperature": "0.0",
                "response_format": "json"
            }

            response = requests.post(
                f"http://127.0.0.1:{WHISPER_SERVER_PORT}/inference",
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("text", "").strip()
        except Exception as e:
            log(f"⚠️  Server request failed: {e} - falling back to CLI")
    elif _whisper_server_process and _whisper_server_process.poll() is not None:
        # Server died - clean up and mark for restart on next fallback
        log("⚠️  Server process died - cleaning up")
        with _whisper_server_lock:
            _whisper_server_process = None

    # Fallback to CLI mode (loads model each time)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        cmd = [WHISPER_CPP_PATH]
        if WHISPER_MODEL_PATH:
            cmd.extend(["-m", WHISPER_MODEL_PATH])
        cmd.extend(["-f", temp_path, "--no-timestamps", "--best-of", "5", "--beam-size", "5", "--language", "en"])

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

            # Start server on first fallback (lazy initialization)
            start_whisper_server()

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
    """Copy text to clipboard, paste it, and optionally restore previous clipboard contents."""
    old_clipboard = None

    # Save current clipboard if preservation is enabled
    if PRESERVE_CLIPBOARD:
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

    if PRESERVE_CLIPBOARD and old_clipboard is not None:
        # Wait for paste to complete before restoring clipboard
        time.sleep(0.5)

        # Restore original clipboard after paste completes
        set_clipboard(old_clipboard)
        log(f"♻️  Restored clipboard: {old_clipboard[:50]}{'...' if len(old_clipboard) > 50 else ''}")

    # Automatically press Enter/Return if enabled
    if AUTO_PRESS_ENTER:
        time.sleep(0.1)  # Brief pause to ensure paste completes
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to key code 36'  # 36 is Return key
        ])
        log("⏎  Pressed Enter")

    # Play sound AFTER clipboard operations complete
    sound("Glass")


class DictationListener:
    def __init__(self):
        self.recorder = None  # Will be created fresh for each recording
        self.is_recording = False
        self.pressed_keys = set()
        self._start_auto_reset_checker()

    def on_press(self, key):
        self.pressed_keys.add(key)

        # Check for reset combo: Ctrl+Shift+R
        # Handle both char keys and key codes
        is_r_key = False
        try:
            if hasattr(key, 'char') and key.char and key.char.lower() == 'r':
                is_r_key = True
        except (AttributeError, TypeError):
            pass

        # Also check vk code for 'r' key (vk 15 on macOS)
        try:
            if hasattr(key, 'vk') and key.vk == 15:
                is_r_key = True
        except (AttributeError, TypeError):
            pass

        if RESET_COMBO.issubset(self.pressed_keys) and is_r_key:
            log("🔄 Ctrl+Shift+R detected - resetting")
            self.reset()
            return

        # Toggle recording: press to start, press again to stop
        if key == HOTKEY_KEY:
            if not self.is_recording:
                # Start recording - CREATE FRESH RECORDER EVERY TIME
                log("🎙️  Creating new recorder...")
                self.recorder = Recorder()  # Brand new instance
                self.is_recording = True
                self.recorder.start()
            else:
                # Stop recording (works around lost key release events)
                log("⚙️  Hotkey pressed again - stopping recording")
                self.is_recording = False
                sound("Blow")  # Play sound immediately so user knows it stopped

                # Dispose of recorder and process in background
                old_recorder = self.recorder
                self.recorder = None  # DISPOSE - never reuse

                def stop_and_process():
                    try:
                        if old_recorder:
                            audio_bytes = old_recorder.stop()  # Kills subprocess, reads file
                            if audio_bytes:
                                self._process_audio(audio_bytes)
                    except Exception as e:
                        log(f"⚠️  Error stopping recorder: {e}")

                threading.Thread(target=stop_and_process, daemon=True).start()

    def on_release(self, key):
        self.pressed_keys.discard(key)

        if self.is_recording and key == HOTKEY_KEY:
            self.is_recording = False
            sound("Blow")  # Play sound immediately so user knows it stopped

            # Dispose of recorder and process in background
            old_recorder = self.recorder
            self.recorder = None  # DISPOSE - never reuse

            def stop_and_process():
                try:
                    if old_recorder:
                        audio_bytes = old_recorder.stop()  # Kills subprocess, reads file
                        if audio_bytes:
                            self._process_audio(audio_bytes)
                except Exception as e:
                    log(f"⚠️  Error stopping recorder: {e}")

            threading.Thread(target=stop_and_process, daemon=True).start()

    def _process_audio(self, audio_bytes: bytes):
        text = transcribe(audio_bytes)
        if text:
            paste_text(text)

    def reset(self, reason="Manual (Ctrl+Shift+R)", process_audio=False):
        """Reset recorder - kill subprocess and optionally process audio."""
        log(f"⚙️  Reset triggered: {reason}")

        self.is_recording = False

        # Dispose of the old recorder
        old_recorder = self.recorder
        self.recorder = None  # Next recording will create fresh instance

        # Kill subprocess and optionally process audio in background
        def kill_and_process():
            try:
                if old_recorder:
                    if process_audio:
                        log("💾 Attempting to save stuck recording...")
                        audio_bytes = old_recorder.stop()  # Kills subprocess, extracts audio
                        if audio_bytes:
                            log(f"✅ Recovered {len(audio_bytes)} bytes - transcribing...")
                            self._process_audio(audio_bytes)
                    else:
                        # Just kill it without processing
                        if old_recorder.process and old_recorder.process.is_alive():
                            old_recorder.process.kill()
                            old_recorder.process.join()
            except Exception as e:
                log(f"⚠️  Error during reset: {e}")

        threading.Thread(target=kill_and_process, daemon=True).start()

        notify("Whisper Dictate", "Recorder reset - ready to record")
        sound("Glass")
        log("✅ Recorder reset complete (subprocess will be killed)")

    def _auto_reset_check(self):
        """Periodically check if recording has been stuck for way too long."""
        while True:
            time.sleep(5)  # Check every 5 seconds
            if self.is_recording and self.recorder and self.recorder.start_time:
                elapsed = time.time() - self.recorder.start_time

                # Auto-reset and process the audio if stuck
                if elapsed > AUTO_STOP_TIMEOUT:
                    log(f"⚠️  Recording stuck for {int(elapsed)}s - forcing reset and transcribing")
                    # Play stop sound immediately so user knows recording stopped
                    sound("Blow")
                    self.reset(reason=f"Auto-reset after {int(elapsed)} seconds", process_audio=True)

    def _start_auto_reset_checker(self):
        """Start background thread to monitor for stuck recordings."""
        checker_thread = threading.Thread(target=self._auto_reset_check, daemon=True)
        checker_thread.start()

    def run(self):
        log("=" * 50)
        log("Whisper Dictate")
        log("=" * 50)
        log(f"Backend: {BACKEND}")
        if FALLBACK_TO_LOCAL:
            log(f"Fallback: local whisper.cpp")
        log(f"Hotkey: {get_hotkey_name(HOTKEY_KEY)} (hold to record)")
        log(f"Reset: Ctrl+Shift+R (if stuck recording)")
        log("Press Ctrl+C to quit")
        log("=" * 50)

        # Show startup notification so user knows it's running
        notify("Whisper Dictate", f"Ready! Hold {get_hotkey_name(HOTKEY_KEY)} to dictate")

        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            listener.join()


def main():
    # Set multiprocessing start method for macOS
    multiprocessing.set_start_method('spawn', force=True)

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
            log(f"❌ whisper.cpp CLI not found at: {WHISPER_CPP_PATH}")
            sys.exit(1)
        if not os.path.exists(WHISPER_SERVER_PATH):
            log(f"⚠️  whisper-server not found at: {WHISPER_SERVER_PATH}")
            log(f"   Server mode disabled, will use CLI only (slower)")
        if not os.path.exists(WHISPER_MODEL_PATH):
            log(f"❌ Whisper model not found at: {WHISPER_MODEL_PATH}")
            sys.exit(1)

    # Start idle checker thread for whisper server cleanup
    idle_checker = threading.Thread(target=check_server_idle, daemon=True)
    idle_checker.start()

    # If using local backend, start server immediately
    if BACKEND == "local":
        start_whisper_server()

    listener = DictationListener()
    try:
        listener.run()
    except KeyboardInterrupt:
        log("\n👋 Goodbye!")
        stop_whisper_server()  # Clean shutdown


if __name__ == "__main__":
    main()
