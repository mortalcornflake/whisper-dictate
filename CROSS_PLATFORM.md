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
- [ ] **Phase 2 — `faster-whisper` backend (cross-platform).** New backend with
  the hardware auto-detection above. macOS keeps whisper.cpp; Windows defaults to
  this.
- [ ] **Phase 3 — Windows adapter + tray UI (on Yuen's PC).** `windows.py`
  (`winsound`/bundled wavs, `plyer` toast, Ctrl+V paste, Startup-folder
  autostart). `pystray` tray icon with Idle/Recording status + right-click menu
  (Quit, Reset, Settings) — replaces signal-based reset. Resolve the
  Right Alt / AltGr hotkey question via first-run choice.
- [ ] **Phase 4 — Friendly installer (on Yuen's PC).** PyInstaller (onedir) →
  Inno Setup wizard with Start Menu shortcut + "Run at login" checkbox. Model
  downloads on first launch with a progress bar. Optional GitHub Actions workflow
  to build the installer artifact per release.
- [ ] **Phase 5 — Docs.** Cross-platform README + a dead-simple Windows install
  guide for a non-technical user.

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
