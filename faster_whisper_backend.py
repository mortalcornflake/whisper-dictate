"""faster-whisper transcription backend with hardware auto-detection.

This is the default local engine on Windows (NVIDIA CUDA), sitting alongside the
whisper.cpp backend used on macOS. It picks device, compute type, and model size
automatically based on the available hardware, so the user never has to specify
their GPU. Everything is overridable via env vars.

See docs/FASTER_WHISPER.md for the design and the override knobs:
  DICTATE_DEVICE, DICTATE_COMPUTE_TYPE, WHISPER_MODEL

faster-whisper is imported lazily (inside functions) so this module is safe to
import even when the package isn't installed (e.g. on the macOS dev machine).
"""
import os
import subprocess
import sys
import tempfile
import threading


def _log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Some Windows consoles use a legacy code page (e.g. cp1252) that can't
        # encode emoji; degrade gracefully instead of crashing the model load.
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc), flush=True)


# Lazily-loaded singleton model (loading is expensive; do it once).
_model = None
_model_lock = threading.Lock()


def _add_cuda_dll_dirs():
    """Make the pip-installed CUDA runtime DLLs loadable on Windows.

    The nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels ship the CUDA DLLs inside
    the venv (nvidia/<lib>/bin), but those folders aren't on Windows' DLL search
    path, so ctranslate2 fails with "cublas64_12.dll is not found". Register them
    explicitly before the model loads. No-op off Windows (macOS uses Metal/CPU)."""
    if sys.platform != "win32":
        return
    import importlib.util
    try:
        spec = importlib.util.find_spec("nvidia")
        roots = list(spec.submodule_search_locations) if spec else []
    except Exception:
        roots = []
    added = []
    for root in roots:
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            bindir = os.path.join(root, sub, "bin")
            if os.path.isdir(bindir):
                added.append(bindir)
                try:
                    os.add_dll_directory(bindir)
                except OSError:
                    pass
    # These CUDA libraries load each other by bare name, which resolves via PATH;
    # add_dll_directory alone isn't enough, so prepend the bin dirs to PATH too.
    if added:
        os.environ["PATH"] = os.pathsep.join(added) + os.pathsep + os.environ.get("PATH", "")


def is_available() -> bool:
    """True if the faster-whisper package is importable."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _detect_device() -> str:
    """Return 'cuda' if a working NVIDIA GPU is present, else 'cpu'.
    Overridable with DICTATE_DEVICE."""
    forced = os.environ.get("DICTATE_DEVICE")
    if forced:
        return forced.lower()
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _detect_vram_gb():
    """Best-effort total VRAM of the first CUDA device, in GB. None if unknown."""
    # Preferred: NVML (via the nvidia-ml-py package, imported as pynvml).
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return info.total / (1024 ** 3)
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        pass
    # Fallback: parse nvidia-smi.
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            mb = int(out.stdout.strip().splitlines()[0])
            return mb / 1024
    except Exception:
        pass
    return None


def _choose_compute_type(device: str) -> str:
    """Pick a compute type for the device. Overridable with DICTATE_COMPUTE_TYPE."""
    forced = os.environ.get("DICTATE_COMPUTE_TYPE")
    if forced:
        return forced
    return "float16" if device == "cuda" else "int8"


def _choose_model(device: str, vram_gb) -> str:
    """Pick a model size from available VRAM (or default for CPU).
    Overridable with WHISPER_MODEL."""
    forced = os.environ.get("WHISPER_MODEL")
    if forced:
        return forced
    if device == "cuda":
        if vram_gb is None:
            # Unknown VRAM but a GPU exists: assume capable; compute-type
            # fallback below will downshift to int8 if memory is tight.
            return "large-v3-turbo"
        if vram_gb >= 6:
            return "large-v3-turbo"
        if vram_gb >= 4:
            return "medium"
        return "small.en"
    # CPU: keep it responsive rather than maximally accurate.
    return "base.en"


def _load_model():
    """Load (once) and return the WhisperModel, configured for the detected
    hardware. Raises RuntimeError with an install hint if the package is missing."""
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. Install it with: "
                "pip install faster-whisper"
            )

        # On Windows, make the pip-installed CUDA DLLs discoverable before load.
        _add_cuda_dll_dirs()

        device = _detect_device()
        vram_gb = _detect_vram_gb() if device == "cuda" else None
        model_name = _choose_model(device, vram_gb)
        compute_type = _choose_compute_type(device)

        vram_str = f"{vram_gb:.1f}GB" if vram_gb is not None else "unknown"
        _log(f"🧠 faster-whisper: device={device} vram={vram_str} "
             f"model={model_name} compute={compute_type}")

        # Try the chosen compute type, then fall back through progressively
        # safer options if the hardware rejects it.
        candidates = [compute_type]
        for ct in ("int8_float16", "int8", "float32"):
            if ct not in candidates:
                candidates.append(ct)

        last_err = None
        for ct in candidates:
            try:
                _model = WhisperModel(model_name, device=device, compute_type=ct)
                if ct != compute_type:
                    _log(f"⚠️  compute_type {compute_type} unavailable; using {ct}")
                return _model
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"Failed to load faster-whisper model: {last_err}")


def warmup():
    """Load the model ahead of time so the first dictation isn't slow.
    Safe to call in a background thread; logs instead of raising."""
    try:
        _load_model()
        _log("✅ faster-whisper model ready")
    except Exception as e:
        _log(f"⚠️  faster-whisper warmup failed: {e}")


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe WAV audio bytes. Raises RuntimeError on failure (so the core
    can handle fallback consistently with the other backends)."""
    model = _load_model()

    # Write to a temp file: a path is the most robust input to faster-whisper.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        segments, _info = model.transcribe(
            temp_path,
            language="en",
            beam_size=5,
            temperature=0.0,
        )
        return "".join(segment.text for segment in segments).strip()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
