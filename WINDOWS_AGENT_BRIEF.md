# Brief for a Claude Code session on the Windows PC

**You are a fresh Claude Code session running on a Windows 11 PC. You have no
memory of the prior planning conversation and you're signed in under a different
account.** This document, plus the files it points to, is everything you need.
Read it fully before acting.

## What this project is

Whisper Dictate: a push-to-talk dictation tool. Hold a hotkey, speak, release →
it records the mic, transcribes with Whisper, and pastes the text at the cursor.
It already works on macOS. **Your job is to make it work — and be friendly to
install — on Windows.**

The end user is **Yuen**, a non-technical person who owns this PC. She has an
**NVIDIA GPU**. The finished Windows experience must be a **one-click installer +
a visible system-tray app**, not an invisible background process.

## Read these, in order

1. **`CROSS_PLATFORM.md`** — the authoritative plan, architecture, and phase list.
2. **`docs/FASTER_WHISPER.md`** — the local transcription engine + GPU auto-detect.
3. **`WINDOWS_SETUP.md`** — how to bootstrap Python/venv/deps on this machine.

## Current state (do not redo)

- **Phase 1 ✅** — macOS-specific OS calls are abstracted behind the `platform_io`
  package. `platform_io/darwin.py` is the macOS implementation;
  `platform_io/windows.py` is a **stub that raises NotImplementedError** — that's
  your Phase 3 work.
- **Phase 2 ✅** — `faster_whisper_backend.py` is the CUDA-capable local engine,
  wired into `dictate.py` as `DICTATE_BACKEND=faster-whisper`, with hardware
  auto-detection. Verified on CPU on the dev Mac; **not yet verified on this PC's
  GPU — that's your first task.**

## The platform_io contract (what Phase 3 must implement)

`platform_io/__init__.py` selects the backend by `sys.platform` and re-exports
these functions. Your `platform_io/windows.py` must implement all of them with
the same signatures as `platform_io/darwin.py`:

- `play_sound(event, blocking=False)` — `event` is one of `"start"`, `"stop"`,
  `"done"`, `"warning"`. macOS maps these to system sounds; on Windows use
  `winsound.PlaySound` with bundled `.wav` files (add them to the repo) or
  `winsound.MessageBeep` as a fallback.
- `notify(title, message)` — a desktop notification (use `win11toast` or `plyer`).
- `send_paste()` — simulate **Ctrl+V** (use `pynput`'s `keyboard.Controller`).
- `send_enter()` — simulate the Enter key (pynput).
- `register_external_reset(callback)` — **no-op on Windows** (there's no SIGUSR1;
  reset comes from the tray menu instead). The stub already does this correctly.

## Your task list

1. **Validate the GPU first (highest priority, lowest effort).** Follow
   `WINDOWS_SETUP.md` to set up the venv and run `python check_setup.py`. Confirm
   it reports `device detected : cuda` and transcribes correctly. Report the
   result. If it falls back to CPU, debug the CUDA wheels / driver before moving
   on — there's no point building UI on a broken engine.
2. **Phase 3** — implement `platform_io/windows.py` (above) and a **`pystray`**
   system-tray app: an icon showing Idle/Recording, with a right-click menu
   (Quit, Reset, Settings). The tray's Reset replaces the macOS signal-based
   reset. Resolve the hotkey: **Right Alt doubles as AltGr** on some layouts and
   can misbehave — make the hotkey a first-run choice rather than a hard default.
   Test the full `dictate.py` end-to-end on Windows.
3. **Phase 4** — package with **PyInstaller** (onedir) and wrap with **Inno
   Setup** into an `.exe` wizard (Start Menu shortcut + "Run at login" checkbox).
   Have the model download on first launch with a progress indicator. Note: the
   unsigned installer will trigger a "Windows protected your PC" SmartScreen
   prompt — document the "More info → Run anyway" step for Yuen.
4. **Phase 5** — write a dead-simple, non-technical Windows install guide for
   Yuen, and update the README for cross-platform.

## Hard constraints

- **Do not break macOS.** The shared core (`dictate.py`, `faster_whisper_backend.py`)
  and `platform_io/darwin.py` must keep working. Make Windows changes additive;
  put Windows-only code in `platform_io/windows.py` and Windows-only files.
- Keep the existing code style: simple, short functions, no over-engineering.
- Update the phase checkboxes in `CROSS_PLATFORM.md` as you complete work.

## Getting your work back to the repo

The code likely arrived here as a **ZIP (no git history)**, and you're on a
different GitHub login. To push your work back to `github.com/mortalcornflake/
whisper-dictate`, you'll need git installed and push access — **coordinate with
the owner (Aaron) on this**; don't assume you can push. Until then, commit
locally if git is available, or keep changes ready to hand back. Confirm the
approach with the user before attempting any push.
