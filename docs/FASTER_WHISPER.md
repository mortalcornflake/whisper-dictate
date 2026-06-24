# faster-whisper backend

This is the local transcription engine for the Windows build. It is **added
alongside** whisper.cpp, not a replacement.

## What it is

[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) is a
reimplementation of OpenAI's Whisper that runs on
[CTranslate2](https://github.com/OpenNMT/CTranslate2), a fast inference engine.

- Same models as Whisper, including `large-v3` and `large-v3-turbo`.
- Roughly **4× faster** than the reference `openai-whisper`, with lower memory.
- Runs on **CPU and NVIDIA GPU (CUDA)**; supports `float16` and `int8`
  quantization.
- `pip install faster-whisper` — **no compilation**. Models auto-download from
  Hugging Face on first use and are cached locally.

## Why faster-whisper on Windows (and not whisper.cpp)

Building whisper.cpp with CUDA on Windows requires Visual Studio + CMake + the
CUDA Toolkit — a non-starter for a non-technical user and painful to set up
remotely. faster-whisper is pip-only and detects the GPU automatically. On macOS
we keep whisper.cpp (Metal) because it's already installed and working.

| | macOS | Windows |
|---|---|---|
| Default local engine | whisper.cpp (Metal) | faster-whisper (CUDA) |
| Install | `install.sh` builds whisper.cpp | `pip install faster-whisper` |
| Acceleration | Apple Metal | NVIDIA CUDA |

Both are selectable on either platform via `DICTATE_BACKEND`; these are just the
sensible defaults.

## GPU dependencies on Windows

CTranslate2's CUDA path needs cuBLAS and cuDNN. On Windows these ship as pip
wheels (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) or can be bundled into the
installer, so the end user installs nothing manually. If no working GPU is
found, it falls back to CPU automatically.

## Hardware auto-detection (no manual GPU config)

The backend configures itself at startup. You do **not** need to know which GPU
Yuen has. Order of decisions:

1. **Device** — probe for a working CUDA device (via CTranslate2 / a guarded
   `device="cuda"` init). If found → `cuda`, else → `cpu`.
2. **Compute type** — `cuda` → `float16`, falling back to `int8_float16` then
   `int8` if the GPU rejects it or VRAM is tight. `cpu` → `int8`.
3. **Model size** — picked from available VRAM (or system RAM on CPU):
   - capable GPU (≈≥6 GB) → `large-v3-turbo`
   - low-VRAM GPU (≈4–6 GB) → `large-v3-turbo` int8 or `medium`
   - very low VRAM / CPU-only → `small.en` / `base.en` for responsiveness
4. It **logs the detected device, VRAM, and chosen model/compute type** so the
   decision is transparent and debuggable.

### Overrides

All automatic; all overridable via `.env`:

```bash
DICTATE_BACKEND=faster-whisper   # use this engine
DICTATE_DEVICE=cuda              # force cuda | cpu (default: auto)
DICTATE_COMPUTE_TYPE=float16     # force compute type (default: auto)
WHISPER_MODEL=large-v3-turbo     # force model size (default: auto by VRAM)
```

## Latency expectation

On a modern NVIDIA GPU with `large-v3-turbo` + `float16`, transcription of a
short dictation is typically sub-second to a few seconds — comparable to the
macOS whisper.cpp/Metal experience.
