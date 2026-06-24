#!/usr/bin/env python3
"""Setup / hardware check for Whisper Dictate.

Run this after installing dependencies to confirm a machine is ready — especially
on Windows, to verify the NVIDIA GPU is detected and faster-whisper can
transcribe. It does NOT run the full app (which needs the Phase 3 Windows
adapter); it checks the transcription engine in isolation so the GPU path can be
validated first.

Usage:
    python check_setup.py            # detect hardware, load model, 4s mic test
    python check_setup.py audio.wav  # transcribe a WAV file instead of the mic
"""
import os
import sys
import platform

# Make sure the backend module (repo root) is importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_imports():
    section("Dependencies")
    deps = ["numpy", "sounddevice", "pynput", "pyperclip", "requests",
            "dotenv", "faster_whisper"]
    ok = True
    for name in deps:
        try:
            __import__(name)
            print(f"  [ok]   {name}")
        except ImportError as e:
            ok = False
            print(f"  [MISS] {name}  ({e})")
    if not ok:
        print("\nSome packages are missing. Install with:")
        print("  pip install -r requirements.txt -r requirements-windows.txt")
    return ok


def check_engine():
    section("Transcription engine (faster-whisper)")
    try:
        import faster_whisper_backend as fw
    except Exception as e:
        print(f"  [FAIL] could not import backend: {e}")
        return None
    if not fw.is_available():
        print("  [FAIL] faster-whisper not installed")
        return None

    device = fw._detect_device()
    vram = fw._detect_vram_gb() if device == "cuda" else None
    print(f"  device detected : {device}")
    print(f"  VRAM            : {f'{vram:.1f} GB' if vram else 'n/a'}")
    print(f"  model           : {fw._choose_model(device, vram)}")
    print(f"  compute type    : {fw._choose_compute_type(device)}")
    if device == "cuda":
        print("  >>> NVIDIA GPU will be used.")
    else:
        print("  >>> No GPU detected - will run on CPU (works, just slower).")

    print("\n  Loading model (first run downloads it; may take a minute)...")
    try:
        fw._load_model()
        print("  [ok]   model loaded")
        return fw
    except Exception as e:
        print(f"  [FAIL] model failed to load: {e}")
        return None


def record_wav(seconds=4, sample_rate=16000):
    import io
    import wave
    import numpy as np
    import sounddevice as sd
    print(f"\n  Recording {seconds}s - say something now...")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype=np.int16)
    sd.wait()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def check_transcription(fw, wav_path=None):
    section("Transcription test")
    try:
        if wav_path:
            with open(wav_path, "rb") as f:
                audio = f.read()
            print(f"  using file: {wav_path}")
        else:
            audio = record_wav()
        text = fw.transcribe(audio)
        print(f"\n  Result: {text!r}")
        if text:
            print("  [ok]   transcription works!")
        else:
            print("  [warn] empty result (silence or very short audio?)")
    except Exception as e:
        print(f"  [FAIL] transcription failed: {e}")


def main():
    section("Whisper Dictate - setup check")
    print(f"  OS      : {platform.system()} {platform.release()}")
    print(f"  Python  : {sys.version.split()[0]}")
    print(f"  Machine : {platform.machine()}")

    if not check_imports():
        sys.exit(1)
    fw = check_engine()
    if fw is None:
        sys.exit(1)
    wav_path = sys.argv[1] if len(sys.argv) > 1 else None
    check_transcription(fw, wav_path)

    section("Done")
    print("  If the GPU was used and transcription works, you're ready for")
    print("  Phase 3 (the Windows app UI). See CROSS_PLATFORM.md.")


if __name__ == "__main__":
    main()
