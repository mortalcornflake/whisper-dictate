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
import atexit
import tempfile
import threading
import subprocess
import multiprocessing
import signal

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

import platform_io
from platform_io import notify, play_sound, send_paste, send_enter, register_external_reset
import faster_whisper_backend as fw_backend

# Force unbuffered output
def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Some Windows consoles / redirected logs use a legacy code page (cp1252)
        # that can't encode emoji; degrade gracefully instead of crashing.
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc), flush=True)


def maybe_play_sound(event, blocking=False):
    """Play a UI sound for a semantic event, unless sounds are turned off via
    PLAY_SOUNDS=false in the .env."""
    if PLAY_SOUNDS:
        play_sound(event, blocking=blocking)


def _env_int(name, default):
    """Parse an integer env var, falling back to default on a missing/bad value.
    Avoids crashing startup when a non-technical user mistypes a value in .env."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        log(f"⚠️  Invalid {name}={raw!r} in .env; using default {default}")
        return default


def parse_hotkey(key_str):
    """Parse hotkey string from .env to pynput Key object."""
    key_map = {
        'alt_r': keyboard.Key.alt_r,
        'alt_l': keyboard.Key.alt_l,
        'alt_gr': keyboard.Key.alt_gr,  # Right Alt on many Windows keyboards
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
        # alt_gr first: on macOS pynput aliases it to alt_r (same object), so the
        # alt_r entry below must come last to win and show "Right Option". On
        # Windows they're distinct keys, so both labels are correct.
        keyboard.Key.alt_gr: "Right Alt (AltGr)",
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
# Default hotkey is platform-aware: Right Option on macOS, Right Ctrl on Windows
# (Right Alt there is AltGr on many layouts and misbehaves). Override with HOTKEY.
_DEFAULT_HOTKEY = "ctrl_r" if sys.platform == "win32" else "alt_r"
HOTKEY_KEY = parse_hotkey(os.environ.get("HOTKEY", _DEFAULT_HOTKEY))
RESET_COMBO = {keyboard.Key.ctrl, keyboard.Key.shift}  # Ctrl+Shift for reset combo
PRESERVE_CLIPBOARD = os.environ.get("PRESERVE_CLIPBOARD", "true").lower() in ("true", "1", "yes")
AUTO_PRESS_ENTER = os.environ.get("AUTO_PRESS_ENTER", "false").lower() in ("true", "1", "yes")
PLAY_SOUNDS = os.environ.get("PLAY_SOUNDS", "true").lower() in ("true", "1", "yes")  # UI sounds on/off
AUTO_STOP_TIMEOUT = _env_int("AUTO_STOP_TIMEOUT", 300)  # Seconds before auto-stop stuck recordings
AUTO_STOP_WARNING = 10  # Seconds before auto-stop to play warning sound
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1

# Audio input device - set to None for system default, or device name/index
# Examples: "MacBook Pro Microphone", "iMac Microphone", "USB Microphone"
# Tip: Use a specific mic name to dictate through built-in mic while using AirPods for audio
INPUT_DEVICE = os.environ.get("INPUT_DEVICE", None)  # None = system default

# Transcription backend: "groq", "openai", "local", or "faster-whisper".
# faster-whisper (CUDA) is the default on Windows; whisper.cpp ("local") on macOS.
BACKEND = os.environ.get(
    "DICTATE_BACKEND",
    "faster-whisper" if sys.platform == "win32" else "local",
)
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
    "~/whisper.cpp/models/ggml-large-v3-turbo.bin"
))
FALLBACK_TO_LOCAL = os.environ.get("FALLBACK_TO_LOCAL", "true").lower() in ("true", "1", "yes")
WHISPER_SERVER_PORT = 8080  # Port for whisper server
WHISPER_SERVER_IDLE_TIMEOUT = 1800  # Shutdown server after 30 min idle (seconds)

# Global server state (lazy initialization)
_whisper_server_process = None
_whisper_server_last_used = None
_whisper_server_lock = threading.Lock()

# Track all spawned recorder subprocesses for cleanup on exit
_all_recorder_processes = []
_all_recorder_processes_lock = threading.Lock()


def _cleanup_all_subprocesses():
    """Kill all tracked recorder subprocesses. Called on exit."""
    with _all_recorder_processes_lock:
        for proc in _all_recorder_processes:
            try:
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=2)
            except:
                pass
        _all_recorder_processes.clear()
    stop_whisper_server()


def recording_worker(output_path, device_name, sample_rate, channels, ready_event, go_event, stop_event):
    """
    Worker function that runs in a subprocess to record audio.
    Spawned eagerly so imports are pre-loaded. Waits for go_event before recording.
    """
    import numpy as np
    import sounddevice as sd
    import signal
    import sys

    # Wait for parent to signal us to start recording.
    # Use timeout loop to detect parent death (orphan protection).
    parent_pid = os.getppid()
    while not go_event.wait(timeout=5):
        if os.getppid() != parent_pid:
            sys.exit(0)

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
    try:
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype=np.int16,
            device=device_name,
            callback=callback
        )
        stream.start()
    except Exception as e:
        print(f"Audio device error: {e}", file=sys.stderr)
        sys.stderr.flush()
        ready_event.set()  # Unblock parent so it doesn't hang
        return

    # Signal parent that audio stream is active
    ready_event.set()

    try:
        # Record until signaled to stop — via SIGTERM (macOS) or the stop_event
        # (Windows, where terminate() is forceful and skips this cleanup/save).
        while not should_exit and not stop_event.is_set():
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


def trim_trailing_silence(audio_data, sample_rate=16000, threshold=300, buffer_secs=0.3):
    """Remove trailing silence to prevent Whisper hallucinations."""
    if len(audio_data) == 0:
        return audio_data
    abs_audio = np.abs(audio_data.flatten())
    above = np.where(abs_audio > threshold)[0]
    if len(above) == 0:
        return audio_data[:0]  # All silence - return empty to skip transcription
    last_speech = above[-1]
    buffer_samples = int(buffer_secs * sample_rate)
    end = min(last_speech + buffer_samples, len(audio_data))
    return audio_data[:end]


class Recorder:
    """Subprocess-based recorder that can be forcefully killed.
    Spawns subprocess eagerly so imports are pre-loaded before recording starts."""

    def __init__(self):
        self.start_time = None

        # Pre-spawn subprocess so it's ready when user presses hotkey
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.npy', delete=False)
        self.temp_file.close()
        self.ready_event = multiprocessing.Event()
        self.go_event = multiprocessing.Event()
        self.stop_event = multiprocessing.Event()
        self.process = multiprocessing.Process(
            target=recording_worker,
            args=(self.temp_file.name, INPUT_DEVICE, SAMPLE_RATE, CHANNELS,
                  self.ready_event, self.go_event, self.stop_event)
        )
        self.process.start()
        with _all_recorder_processes_lock:
            _all_recorder_processes.append(self.process)

    def start(self):
        self.start_time = time.time()

        # Signal pre-spawned subprocess to start recording (imports already done)
        self.go_event.set()

        # Wait for subprocess to confirm audio stream is active
        if self.ready_event.wait(timeout=3):
            log("🎤 Recording...")
        else:
            log("⚠️  Recording subprocess slow to start")

        maybe_play_sound("start")

    def stop(self) -> bytes:
        """Stop recording subprocess and extract audio."""
        duration = 0
        if self.start_time:
            duration = time.time() - self.start_time

        log(f"⏹️  Stopping recording subprocess (duration: {duration:.1f}s)")

        # Ask the subprocess to stop gracefully so it saves what it recorded.
        # On macOS terminate() (SIGTERM) also triggers the save; on Windows
        # terminate() is forceful and would skip it, so the event is essential.
        if self.process and self.process.is_alive():
            log("🛑 Signaling recording subprocess to stop...")
            self.stop_event.set()
            self.process.join(timeout=5)  # Wait for clean shutdown (saves audio)

            if self.process.is_alive():
                log("🔫 Terminating recording subprocess...")
                self.process.terminate()
                self.process.join(timeout=2)

            if self.process.is_alive():
                log("💀 Force killing stuck subprocess...")
                self.process.kill()  # nuclear option
                self.process.join(timeout=2)

        with _all_recorder_processes_lock:
            if self.process in _all_recorder_processes:
                _all_recorder_processes.remove(self.process)

        # Give subprocess a moment to finish writing file
        time.sleep(0.1)

        # Read the recorded audio from temp file
        audio_bytes = b""
        try:
            if os.path.exists(self.temp_file.name):
                audio_data = np.load(self.temp_file.name)
                audio_data = trim_trailing_silence(audio_data, sample_rate=SAMPLE_RATE)

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
    """Transcribe using OpenAI Whisper API. Raises on error for fallback."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")

    response = requests.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={"model": "whisper-1"},
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(f"OpenAI API error: {response.status_code}")

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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
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
    while True:
        time.sleep(60)  # Check every minute

        # Decide under lock, act outside lock (stop_whisper_server acquires its own lock)
        should_stop = False
        with _whisper_server_lock:
            if _whisper_server_process and _whisper_server_last_used:
                idle_time = time.time() - _whisper_server_last_used
                if idle_time > WHISPER_SERVER_IDLE_TIMEOUT:
                    log(f"💤 Whisper server idle for {int(idle_time/60)}min - shutting down")
                    should_stop = True

        if should_stop:
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

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    finally:
        os.unlink(temp_path)


HALLUCINATION_PHRASES = {
    "thank you", "thank you.", "thanks for watching", "thanks for watching.",
    "okay", "okay.", "you", "you.", "yeah", "yeah.", "yes", "yes.",
}


def _is_hallucination(text: str) -> bool:
    """True if text is a known Whisper phantom phrase (triggered by trailing
    silence). Matched case-insensitively after stripping."""
    return text.strip().lower() in HALLUCINATION_PHRASES


def transcribe_local_fallback(audio_bytes: bytes) -> str:
    """Transcribe with whichever local engine is available — whisper.cpp if it's
    installed (macOS default), otherwise faster-whisper (Windows default). Used as
    the fallback target for cloud backends."""
    if os.path.exists(WHISPER_CPP_PATH) and os.path.exists(WHISPER_MODEL_PATH):
        start_whisper_server()  # lazy server init for whisper.cpp
        return transcribe_local(audio_bytes)
    return fw_backend.transcribe(audio_bytes)


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio using configured backend, with local fallback."""
    log(f"📝 Transcribing with {BACKEND}...")

    result = ""
    try:
        if BACKEND == "groq":
            result = transcribe_groq(audio_bytes)
        elif BACKEND == "openai":
            result = transcribe_openai(audio_bytes)
        elif BACKEND == "local":
            result = transcribe_local(audio_bytes)
        elif BACKEND == "faster-whisper":
            result = fw_backend.transcribe(audio_bytes)
        else:
            log(f"❌ Unknown backend: {BACKEND}")
            return ""
    except (requests.exceptions.RequestException, RuntimeError, ValueError) as e:
        # Only cloud backends fall back to a local engine; the local engines are
        # already the last resort.
        if FALLBACK_TO_LOCAL and BACKEND in ("groq", "openai"):
            log(f"⚠️  Cloud failed ({e}), falling back to local transcription...")
            notify("Whisper Dictate", f"Using local fallback: {e}")
            try:
                result = transcribe_local_fallback(audio_bytes)
            except Exception as fe:
                log(f"❌ Local fallback failed: {fe}")
                notify("Whisper Dictate", f"Transcription failed: {fe}")
                return ""
        else:
            log(f"❌ Transcription failed: {e}")
            notify("Whisper Dictate", f"Transcription failed: {e}")
            return ""

    # Filter known Whisper hallucination phrases (triggered by trailing silence)
    if _is_hallucination(result):
        log(f"Filtered hallucination: {result.strip()}")
        return ""

    return result


def get_clipboard() -> str:
    """Get current clipboard contents (cross-platform via pyperclip).

    pyperclip's macOS pyobjc backend returns None when the clipboard holds
    non-text content (an image or file); coerce to "" so callers always get a
    string (matching the old pbpaste behavior)."""
    return pyperclip.paste() or ""


def set_clipboard(text: str):
    """Set clipboard contents (cross-platform via pyperclip)."""
    pyperclip.copy(text)


def paste_text(text: str):
    """Copy text to clipboard, paste it, and optionally restore previous clipboard contents."""
    old_clipboard = None

    # Save current clipboard if preservation is enabled
    if PRESERVE_CLIPBOARD:
        old_clipboard = get_clipboard()
        log(f"📋 Saved clipboard: {old_clipboard[:50]}{'...' if len(old_clipboard) > 50 else ''}")

    # Copy new text and paste
    pyperclip.copy(text)

    # Simulate the paste shortcut (platform-specific: Cmd+V / Ctrl+V)
    send_paste()
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
        send_enter()
        log("⏎  Pressed Enter")

    # Play sound AFTER clipboard operations complete
    maybe_play_sound("done", blocking=True)


class DictationListener:
    def __init__(self):
        self.recorder = None
        self.is_recording = False
        self.pressed_keys = set()
        self._standby_recorder = None
        self._standby_lock = threading.Lock()
        self._last_hotkey_time = 0  # Debounce key-repeat
        self._start_auto_reset_checker()
        self._prepare_standby()

    def _prepare_standby(self):
        """Pre-spawn a subprocess so it's ready for the next recording."""
        with self._standby_lock:
            # Don't spawn if one already exists
            if self._standby_recorder is not None:
                return
            try:
                self._standby_recorder = Recorder()
                log("🔄 Standby recorder ready")
            except Exception as e:
                log(f"⚠️  Failed to prepare standby recorder: {e}")
                self._standby_recorder = None

    def on_press(self, key):
        # If the key is already held, this is an OS auto-repeat key-down (Windows
        # repeats held keys; macOS doesn't), not a fresh press.
        is_repeat = key in self.pressed_keys
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
            # Ignore auto-repeat key-downs while the key is held, so holding the
            # key records continuously instead of toggling every half-second. A
            # genuine second tap arrives only after a release (key cleared from
            # pressed_keys), so it still works as a stop fallback.
            if is_repeat:
                return
            # Debounce accidental double-fires.
            now = time.time()
            if now - self._last_hotkey_time < 0.5:
                return
            self._last_hotkey_time = now

            if not self.is_recording:
                # Use pre-spawned standby recorder, or create fresh if none available
                if self._standby_recorder:
                    self.recorder = self._standby_recorder
                    self._standby_recorder = None
                else:
                    log("🎙️  No standby ready, spawning new recorder...")
                    self.recorder = Recorder()
                self.is_recording = True
                self._warning_played = False
                self.recorder.start()
            else:
                # Stop recording (works around lost key release events)
                log("⚙️  Hotkey pressed again - stopping recording")
                self._stop_and_process_recording()

    def on_release(self, key):
        self.pressed_keys.discard(key)

        if self.is_recording and key == HOTKEY_KEY:
            self._stop_and_process_recording()

    def _stop_and_process_recording(self):
        """Stop current recording and transcribe in background."""
        self.is_recording = False

        # Dispose of recorder and process in background
        old_recorder = self.recorder
        self.recorder = None  # DISPOSE - never reuse

        def stop_and_process():
            try:
                if old_recorder:
                    audio_bytes = old_recorder.stop()  # Kills subprocess, reads file
                    maybe_play_sound("stop")  # Play after recording stops
                    if audio_bytes:
                        self._process_audio(audio_bytes)
            except Exception as e:
                log(f"⚠️  Error stopping recorder: {e}")

        threading.Thread(target=stop_and_process, daemon=True).start()

    def _process_audio(self, audio_bytes: bytes):
        text = transcribe(audio_bytes).strip()
        if text:
            paste_text(text)
        # Pre-spawn next standby recorder so it's ready for the next recording
        self._prepare_standby()

    def reset(self, reason="Manual (Ctrl+Shift+R)", process_audio=False):
        """Reset recorder - kill subprocess and optionally process audio."""
        log(f"⚙️  Reset triggered: {reason}")

        self.is_recording = False

        # Dispose of the old recorder and standby
        old_recorder = self.recorder
        self.recorder = None
        old_standby = self._standby_recorder
        self._standby_recorder = None

        # Kill subprocess and optionally process audio in background
        def kill_and_process():
            try:
                # Kill standby subprocess and clean up its temp file
                if old_standby:
                    if old_standby.process and old_standby.process.is_alive():
                        old_standby.process.kill()
                        old_standby.process.join(timeout=2)
                    try:
                        if old_standby.temp_file and os.path.exists(old_standby.temp_file.name):
                            os.unlink(old_standby.temp_file.name)
                    except:
                        pass

                if old_recorder:
                    if process_audio:
                        log("💾 Attempting to save stuck recording...")
                        audio_bytes = old_recorder.stop()  # Kills subprocess, extracts audio
                        if audio_bytes:
                            log(f"✅ Recovered {len(audio_bytes)} bytes - transcribing...")
                            self._process_audio(audio_bytes)
                            return  # _process_audio already prepares standby
                    else:
                        # Just kill it without processing
                        if old_recorder.process and old_recorder.process.is_alive():
                            old_recorder.process.kill()
                            old_recorder.process.join()
            except Exception as e:
                log(f"⚠️  Error during reset: {e}")

            # Prepare fresh standby
            self._prepare_standby()

        threading.Thread(target=kill_and_process, daemon=True).start()

        notify("Whisper Dictate", "Recorder reset - ready to record")
        maybe_play_sound("done", blocking=True)
        log("✅ Recorder reset complete (subprocess will be killed)")

    def _auto_reset_check(self):
        """Periodically check if recording has been stuck for way too long."""
        while True:
            time.sleep(5)  # Check every 5 seconds
            # Capture local references to avoid torn state from other threads
            recorder = self.recorder
            if self.is_recording and recorder and recorder.start_time:
                elapsed = time.time() - recorder.start_time

                # Warning sound before auto-stop
                warning_at = AUTO_STOP_TIMEOUT - AUTO_STOP_WARNING
                if not getattr(self, '_warning_played', False) and elapsed > warning_at:
                    self._warning_played = True
                    maybe_play_sound("warning")
                    log(f"⚠️  Recording approaching limit ({AUTO_STOP_WARNING}s remaining)")

                # Auto-reset and process the audio if stuck
                if elapsed > AUTO_STOP_TIMEOUT:
                    self._warning_played = False
                    log(f"⚠️  Recording exceeded {AUTO_STOP_TIMEOUT}s - auto-stopping and transcribing")
                    self.reset(reason=f"Auto-reset after {int(elapsed)} seconds", process_audio=True)

    def _start_auto_reset_checker(self):
        """Start background thread to monitor for stuck recordings."""
        checker_thread = threading.Thread(target=self._auto_reset_check, daemon=True)
        checker_thread.start()

    def _startup_banner(self):
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

    def run(self):
        """Blocking run on the main thread (macOS path — no tray)."""
        self._startup_banner()
        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            listener.join()

    def start_listening(self):
        """Start the keyboard listener WITHOUT blocking, so the caller can use
        the main thread for something else (the Windows tray icon). Returns the
        listener."""
        self._startup_banner()
        self._listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self._listener.start()
        return self._listener

    def stop_listening(self):
        """Stop the keyboard listener started by start_listening()."""
        listener = getattr(self, "_listener", None)
        if listener is not None:
            listener.stop()


def _acquire_single_instance_lock():
    """Ensure only one instance runs on Windows — auto-start plus a manual launch
    could otherwise run two copies that both type. Returns a handle to keep alive
    for the process lifetime, or None. Exits if another instance already holds the
    lock. No-op on non-Windows (macOS unaffected)."""
    if sys.platform != "win32":
        return None
    import ctypes
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Local\\WhisperDictateSingleton")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        log("Another instance is already running - exiting this one.")
        notify("Whisper Dictate", "Already running - see the tray icon by your clock.")
        time.sleep(2)  # let the notification appear before we exit
        sys.exit(0)
    return handle


def main():
    # Set multiprocessing start method for macOS
    multiprocessing.set_start_method('spawn', force=True)

    # Only allow one running instance (Windows): keep the handle alive for the
    # lifetime of main() so the lock is held until the app exits.
    _single_instance_handle = _acquire_single_instance_lock()

    # Check for required configuration based on backend
    if BACKEND == "local":
        # Local mode: just verify whisper.cpp paths exist
        if not os.path.exists(WHISPER_CPP_PATH):
            log(f"❌ whisper.cpp CLI not found at: {WHISPER_CPP_PATH}")
            log(f"   Run install.sh to set up local transcription")
            sys.exit(1)
        if not os.path.exists(WHISPER_SERVER_PATH):
            log(f"⚠️  whisper-server not found at: {WHISPER_SERVER_PATH}")
            log(f"   Server mode disabled, will use CLI only (slower)")
        if not os.path.exists(WHISPER_MODEL_PATH):
            log(f"❌ Whisper model not found at: {WHISPER_MODEL_PATH}")
            log(f"   Run install.sh to download a model")
            sys.exit(1)
    elif BACKEND == "groq" and not GROQ_API_KEY:
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
    elif BACKEND == "faster-whisper":
        if not fw_backend.is_available():
            log("❌ faster-whisper backend selected but the package isn't installed.")
            log("   Install it with: pip install faster-whisper")
            sys.exit(1)

    # Verify a local fallback engine exists for cloud backends.
    if FALLBACK_TO_LOCAL and BACKEND in ("groq", "openai"):
        have_whisper_cpp = os.path.exists(WHISPER_CPP_PATH) and os.path.exists(WHISPER_MODEL_PATH)
        if not have_whisper_cpp and not fw_backend.is_available():
            log(f"⚠️  No local fallback available (whisper.cpp not found at {WHISPER_CPP_PATH},")
            log(f"   and faster-whisper not installed) — running cloud-only.")

    # Start idle checker thread for whisper server cleanup
    idle_checker = threading.Thread(target=check_server_idle, daemon=True)
    idle_checker.start()

    # If using a local backend, get it ready up front.
    if BACKEND == "local":
        start_whisper_server()
    elif BACKEND == "faster-whisper":
        # Warm up the model in the background so the first dictation is fast.
        threading.Thread(target=fw_backend.warmup, daemon=True).start()

    # Register cleanup for all exit paths
    atexit.register(_cleanup_all_subprocesses)

    def sigterm_handler(signum, frame):
        log("\n🛑 SIGTERM received - cleaning up...")
        _cleanup_all_subprocesses()
        os._exit(0)
    signal.signal(signal.SIGTERM, sigterm_handler)

    listener = DictationListener()

    # Register external reset handler (force-reset.sh sends SIGUSR1 on macOS;
    # on Windows this is a no-op and reset comes from the tray menu instead).
    def on_external_reset():
        log("🔄 External reset signal received - resetting recorder")
        listener.reset(reason="External reset signal")
    register_external_reset(on_external_reset)

    if sys.platform == "win32":
        # Windows: the tray icon owns the main thread; the keyboard listener runs
        # in the background. run_with_tray() blocks until the user picks Quit.
        from tray_app import run_with_tray
        try:
            run_with_tray(listener)
        except KeyboardInterrupt:
            pass
        log("\n👋 Goodbye!")
        _cleanup_all_subprocesses()
    else:
        try:
            listener.run()
        except KeyboardInterrupt:
            log("\n👋 Goodbye!")
            _cleanup_all_subprocesses()


if __name__ == "__main__":
    # Required for PyInstaller-frozen builds using multiprocessing 'spawn'
    # (Phase 4); a no-op when running normally.
    multiprocessing.freeze_support()
    main()
