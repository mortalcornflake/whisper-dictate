# Brief for a Claude Code session on the Windows PC

**You are a Claude Code session running on a Windows 11 PC, picking up the Windows
build of this project.** This document, plus the files it points to, is everything
you need — read it fully before acting (you may have no memory of the prior work).

## What this project is

Whisper Dictate: a push-to-talk dictation tool. Hold a hotkey, speak, release →
it records the mic, transcribes with Whisper, and pastes the text at the cursor.
It works on **both macOS and Windows today**. The Windows core (Phase 3) is done;
what remains is **packaging it into a friendly installer (Phase 4) and user docs
(Phase 5)**.

The eventual end user is **Yuen**, a non-technical person with an NVIDIA GPU — the
finished Windows deliverable must be a **one-click installer + a visible
system-tray app**. Active Windows development now happens on the **owner's own
Windows PC** (so a fresh clone here should just work, and you can push to the
owner's repo once git is set up).

## Read these, in order

1. **`CROSS_PLATFORM.md`** — the authoritative plan, architecture, and phase list.
2. **`docs/FASTER_WHISPER.md`** — the local transcription engine + GPU auto-detect.
3. **`WINDOWS_SETUP.md`** — how to bootstrap Python/venv/deps on this machine.

## Current state (DONE — do not redo)

- **Phase 1 ✅** — macOS OS calls abstracted behind the `platform_io` package.
- **Phase 2 ✅** — `faster_whisper_backend.py`, the CUDA local engine, with
  hardware auto-detection.
- **Phase 3 ✅ (merged to `main`)** — `platform_io/windows.py` (winsound,
  win11toast, pynput Ctrl+V), `tray_app.py` (pystray Idle/Recording icon +
  Reset/Settings/Quit), Windows single-instance lock, event-based graceful
  subprocess stop, encoding-safe logging, CUDA-DLL discovery, and
  `start-dictate.vbs`/`.bat` for hidden auto-start. Verified end-to-end on a
  Windows NVIDIA PC: Right Ctrl → CUDA transcription → paste.
- **Review hardening ✅ (this session)** — platform-aware `HOTKEY` default
  (`ctrl_r` on Windows), `requirements.txt` pyobjc markers so `pip install` works
  on Windows, guarded `.env` int parsing, `multiprocessing.freeze_support()` for
  PyInstaller, plus a `tests/` unit suite and a GitHub Actions CI matrix
  (macOS + Windows).

**First thing to do here:** clone, set up per `WINDOWS_SETUP.md`, and run
`python check_setup.py` to confirm this PC's GPU is used (`device detected : cuda`),
then `venv\Scripts\python.exe dictate.py` to confirm the app runs.

## What's left

**Phase 4 — friendly installer (the main remaining work).** Done so far: the
auto-start launcher + single-instance lock. Still to do:
- **PyInstaller** onedir build of `dictate.py`. Gotchas already handled in code:
  `multiprocessing.freeze_support()` is in place; the spec must **bundle the
  NVIDIA CUDA runtime DLLs** (`nvidia/<cublas|cudnn|cuda_nvrtc>/bin`) and
  `tray_app.py` + `platform_io`.
- **Inno Setup** `.exe` wizard: Start Menu + Desktop shortcuts, a "Run at login"
  checkbox (writes the Startup shortcut), and uninstall.
- **First-launch model download with a progress bar** — a fresh user otherwise
  waits several silent minutes while faster-whisper pulls ~1.5 GB from Hugging
  Face. Surface progress in the tray/a window.
- **Code signing** (or at minimum document the SmartScreen "More info → Run
  anyway" step for the unsigned `.exe`).

**Phase 5 — docs.** A dead-simple, non-technical Windows install/usage guide, and
a cross-platform README rewrite (the dated "Windows port — status" block in the
README should move into `CROSS_PLATFORM.md`).

**Nice-to-haves (optional, from the project review):** macOS menu-bar parity
(`rumps`) so macOS gets the same visible icon; a real settings dialog instead of
the tray "Settings" opening raw `.env`; `logging` with rotation instead of an
ever-growing log file.

## Hard constraints

- **Do not break macOS.** The shared core (`dictate.py`, `faster_whisper_backend.py`)
  and `platform_io/darwin.py` must keep working. Make Windows changes additive;
  put Windows-only code in `platform_io/windows.py` and Windows-only files.
- Keep the existing code style: simple, short functions, no over-engineering.
- Update the phase checkboxes in `CROSS_PLATFORM.md` as you complete work.

## Getting your work back to the repo

The repo is public: `git clone https://github.com/mortalcornflake/whisper-dictate`
works without auth. Windows development now runs on the **owner's own PC**, so once
git is set up and authenticated here, commit and push to `main` normally (clear
messages, keep macOS working — CI runs on macOS + Windows on every push). Do the
Phase 4 packaging work on a branch if you want to keep `main` shippable.
