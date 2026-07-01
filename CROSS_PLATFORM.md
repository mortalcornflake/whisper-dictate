# Cross-Platform Plan (macOS + Windows)

> **Read this first if you're a future session.** This is the authoritative plan
> for turning Whisper Dictate into a single cross-platform, local-first dictation
> tool that runs on macOS (existing) and Windows (new). It persists the decisions
> and rationale from the planning session so work can continue after compaction.

## Goal

One open-source dictation tool, **one repo**, local-first inference with optional
cloud backends. The immediate driver: a friendly Windows build for a non-technical
user (Yuen) who has an **NVIDIA GPU**. The Windows experience must be a one-click
installer + a visible system-tray app — not an invisible background process.

## Decision: single cross-platform repo (not a fork)

The macOS-specific surface is small (~5% of `dictate.py`). The valuable core —
recording-subprocess lifecycle, backend fallback, silence trimming, the
hallucination filter, config, the toggle-mode hotkey state machine — is
platform-neutral and must stay in sync. A second repo would duplicate that and
let it drift. So: shared core + a thin per-OS adapter layer.

**Pros:** one source of truth, fixes/features land on both platforms, clean
open-source story. **Cons:** an upfront (incremental) refactor, plus we maintain a
Windows path that the macOS owner can't dogfood — so it must stay simple and be
tested on the real machine.

### Architecture

```
dictate.py            # platform-neutral core (recording, transcription, paste orchestration)
platform_io/          # OS adapter package — NOTE: not named "platform" (stdlib clash)
  __init__.py         # selects backend by sys.platform, re-exports the interface
  darwin.py           # macOS: afplay, osascript, SIGUSR1
  windows.py          # Windows: winsound, toast, pynput paste (Phase 3)
backends/ (future)    # transcription engines if the file grows
```

**Adapter interface** (`platform_io`): `play_sound(event, blocking)`,
`notify(title, message)`, `send_paste()`, `send_enter()`,
`register_external_reset(callback)`. Clipboard get/set stays in the core via
`pyperclip` (already cross-platform), so it is *not* part of the adapter.

`play_sound` takes **semantic events** (`"start"`, `"stop"`, `"done"`,
`"warning"`) so each OS maps them to its own sounds.

## Transcription backends

`DICTATE_BACKEND` selects the engine. Local-first; cloud is opt-in.

| Backend | Engine | Platform role |
|---|---|---|
| `local` | whisper.cpp (Metal) | macOS default — already set up, unchanged |
| `faster-whisper` | faster-whisper / CTranslate2 (CUDA) | **Windows default** (NEW, Phase 2) |
| `groq` | Groq API | optional cloud, both |
| `openai` | OpenAI API | optional cloud, both |

**faster-whisper sits alongside whisper.cpp — it does not replace it.** See
`docs/FASTER_WHISPER.md` for the full write-up and the hardware auto-detection
design.

### Hardware auto-detection (no manual GPU config)

The `faster-whisper` backend detects hardware at startup and configures itself.
Everything is overridable by env var, but defaults are automatic:

- **Device:** use CUDA if a working NVIDIA GPU is found, else CPU.
- **Compute type:** GPU → `float16` (fall back to `int8_float16`/`int8`);
  CPU → `int8`.
- **Model size by VRAM/RAM:** large-v3-turbo on capable GPUs; smaller models
  (`small.en`/`base.en`) on low-VRAM GPUs or CPU.
- It **logs what it detected and chose** so the behavior is transparent.

Overrides: `DICTATE_DEVICE`, `DICTATE_COMPUTE_TYPE`, `WHISPER_MODEL`.

## Phased plan

Each phase keeps the macOS app working at every commit.

- [x] **Phase 1 — Platform abstraction (macOS, verifiable on the Mac).** ✅ DONE
  Created `platform_io/` with `darwin.py` (+ `windows.py` stub); moved
  `osascript`/`afplay` calls behind it; clipboard via `pyperclip`; guarded the
  SIGUSR1 reset behind `register_external_reset`. macOS behavior unchanged;
  verified the refactor compiles, imports, and resolves to the darwin backend.
- [x] **Phase 2 — `faster-whisper` backend (cross-platform).** ✅ DONE
  Added `faster_whisper_backend.py` (lazy model load, env overrides) wired into
  `dictate.py` as the `faster-whisper` backend, with hardware auto-detection
  (device/VRAM → model + compute type) and progressive compute-type fallback.
  Cloud backends now fall back to whichever local engine is present (whisper.cpp
  preferred, else faster-whisper). Added `requirements-windows.txt` and `.env`
  docs. Verified end-to-end on CPU: real speech transcribed correctly.
- [x] **Phase 3 — Windows adapter + tray UI (on Yuen's PC).** ✅ DONE
  Implemented `platform_io/windows.py` (winsound system sounds, win11toast
  notifications, pynput Ctrl+V paste / Enter). Added `tray_app.py`: a `pystray`
  tray icon with Idle (grey) / Recording (red) status and a right-click menu
  (Reset / Settings / Quit) — the tray Reset replaces the signal-based reset.
  `dictate.py` now defaults to the faster-whisper backend on Windows and runs the
  keyboard listener in a background thread while the tray owns the main thread.
  Fixed Windows-specific issues found in testing: emoji-print crash and CUDA DLL
  discovery (in `faster_whisper_backend.py`), the held-key auto-repeat that
  toggled recording, and graceful subprocess stop (event-based) so audio saves
  on Windows where terminate() is forceful. Hotkey is a `.env` choice
  (Right Ctrl chosen, avoiding the Right Alt / AltGr issue). Verified end-to-end
  on Yuen's PC: speech → CUDA transcription → paste. Still TODO for the installer
  phase: Startup-folder autostart.
- [~] **Phase 4 — Friendly installer (on the owner's Windows PC).** Done: hidden
  auto-start launcher (`start-dictate.vbs`/`.bat`) + single-instance lock +
  `freeze_support()`. TODO: PyInstaller (onedir, bundling the NVIDIA CUDA runtime
  DLLs + `tray_app`/`platform_io`) → Inno Setup wizard (Start Menu/Desktop
  shortcuts, "Run at login" checkbox, uninstall); first-launch model download with
  a progress bar; code signing (or document the SmartScreen prompt).
- [ ] **Phase 5 — Docs.** Cross-platform README + a dead-simple Windows install
  guide for a non-technical user. (Move the dated "Windows port — status" block
  out of the README into this file.)
- [ ] **Phase 6 — Windows tray parity with the macOS menu (NEW, Jun 2026).** The
  macOS menu bar (`menubar_app.py`) grew a lot of UI that the Windows tray
  (`tray_app.py`) does NOT yet have. **The underlying features are all in the
  cross-platform core and already work on Windows — only the tray *menu* is
  behind.** Bring `tray_app.py` up to parity (pystray supports checkbox items via
  `MenuItem(..., checked=lambda item: <bool>)` and radio groups via `radio=True`):
  - **Sounds submenu** — toggle each key in `dictate.SOUNDS_ENABLED` live +
    persist to `.env`.
  - **Hands-free toggle + Pasting toggles** — the three `dictate.LIVE_SETTINGS`
    booleans (`hands_free`, `preserve_clipboard`, `auto_press_enter`), live +
    persisted. (Hands-free latch itself is core logic and already works: hold
    Shift + tap the hotkey to start, tap the hotkey to stop. On Windows pynput
    reports `shift_l`/`shift_r`; `resolve_modifier_keys("shift")` already covers
    both — verify on the PC.)
  - **Transcription backend** radio — write `DICTATE_BACKEND`, then a toast saying
    "restart to apply" (backend is read once at startup).
  - **Help & about** — mirror macOS: write the guide to a temp `.txt` and
    `os.startfile()` it (Notepad), rather than a modal dialog.
  - **Plumbing:** `run_with_tray()` must accept `sound_config`, `live_settings`,
    `backend`, `hotkey_name`, `hands_free_modifier` (like `run_with_menubar`), and
    `dictate.py`'s win32 branch must pass them. The pure `.env` helpers
    (`upsert_env_line` / `persist_env_setting` / `ensure_env_file`) currently live
    in `menubar_app.py` — **extract them to a shared, import-safe module** (e.g.
    `settings_io.py`) so the tray can reuse them without importing the rumps
    module. Keep it additive; don't break macOS.

### Testing & CI (added during the project review)

- `tests/` — pytest unit suite for the pure logic (`trim_trailing_silence`,
  hallucination filter, `get_clipboard` None-coercion, `parse_hotkey`, `_env_int`,
  and the faster-whisper model/compute/device selection).
- `.github/workflows/ci.yml` — runs the suite on **macOS + Windows** per push/PR.
  Installing `requirements.txt` on the Windows runner also regression-tests that
  the macOS-only pyobjc deps are correctly skipped there.
- Run locally: `pip install -r requirements.txt -r requirements-dev.txt && pytest`.

### Review hardening (done)

Platform-aware `HOTKEY` default (`ctrl_r` on Windows, avoiding AltGr);
`requirements.txt` pyobjc markers (cross-platform `pip install`); guarded `.env`
int parsing; `multiprocessing.freeze_support()` for PyInstaller.

## Windows tech stack (chosen)

- **Language:** Python (reuse the entire core).
- **Local inference:** `faster-whisper` (pip, CUDA auto, no compilation — avoids
  the Visual Studio + CUDA Toolkit pain of building whisper.cpp on Windows).
- **Hotkey/audio:** `pynput` + `sounddevice` (already used; both cross-platform).
- **Clipboard:** `pyperclip` (cross-platform).
- **Paste keystroke:** osascript Cmd+V on macOS (proven, kept); `pynput`
  controller Ctrl+V on Windows.
- **Sounds:** `afplay` (macOS) / `winsound` or bundled `.wav` (Windows).
- **Notifications:** osascript (macOS) / `plyer` toast (Windows).
- **Tray UI:** `pystray` + `Pillow`.
- **Packaging:** PyInstaller → Inno Setup `.exe` wizard.
- **Autostart:** Login Item (macOS, manual) / Startup-folder shortcut (Windows).

## Open questions / gotchas

- **Right Alt = AltGr** on some Windows keyboard layouts and can misbehave; make
  the hotkey a first-run choice rather than a hard default.
- **SIGUSR1 does not exist on Windows** — external reset there comes from the tray
  menu, not a signal.
- **Build/test loop:** the macOS owner runs Claude on the Mac; Windows-only phases
  (3–5) are best done with Claude Code running directly on Yuen's PC.
