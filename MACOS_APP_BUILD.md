# Build a standalone macOS `.app` for Whisper Dictate (PyInstaller)

> Status: **Shelved (2026-07-05)** — design complete, not yet implemented. Picked back
> up when the hallucination work is sorted. Original Claude plan preserved verbatim
> below as the implementation spec.

## Context

**The problem.** After a MacBook reboot the app fails to auto-start / the hotkey is
dead. Per `CLAUDE.md`'s leading hypothesis, the Login Item runs `venv/bin/python`,
which resolves to the **Command Line Tools framework Python** — a binary that OS / CLT
updates silently replace, **invalidating its TCC grants** (Input Monitoring +
Accessibility) → `"This process is not trusted!"` → dead hotkey. The current manual
launch also requires `cd` + `source venv/bin/activate` + `python dictate.py`.

**The fix.** Bundle the app **and its own Python interpreter** into a real `.app`
via PyInstaller. The binary is then stable — not replaced by OS updates — so TCC
grants stick to it. Side benefits: double-click / Spotlight / Launchpad launch, no
Terminal, no venv. This is the same tool already planned for the Windows installer
(Phase 4), so the effort transfers.

**Why this is NOT the old failed pattern.** The historical `WhisperDictate.app` was a
*thin wrapper* that still launched the CLT Python under the hood → same TCC problem.
This is a full PyInstaller bundle with its own embedded interpreter.
`CLAUDE.md`'s "do NOT re-create the app-bundle LaunchAgent" warning is about the
*LaunchAgent*, not a real packaged app — a clarifying note will be added there.

**Intended outcome.** A signed `Whisper Dictate.app` in `/Applications` that launches
like any Mac app, holds durable TCC grants, and can replace `start-dictate.sh` as the
Login Item so auto-start finally survives reboots.

---

## Approach

PyInstaller **onedir** (not onefile — required for reliable `multiprocessing` spawn,
which the recorder subprocess uses, and matches the Windows plan). Ad-hoc code signing
(free, sufficient for local use). External resources (whisper.cpp binaries, the ~1.5 GB
model, recordings, log) stay external — they're already env-path-driven.

The one behavioural change: **`.env` moves to a stable, writable, user-owned location
when frozen**, because the bundle's `Contents/` is read-only after signing and we must
not bake the owner's Groq API key into a shipped bundle.

### 1. New `app_paths.py` — frozen-aware path resolver

Single small module imported by both `dictate.py` and `menubar_app.py` (no circular
import — neither imports the other at module load today):

- `is_frozen()` → `getattr(sys, "frozen", False)`
- `app_support_dir()` → when frozen: `~/Library/Application Support/WhisperDictate/`;
  when not frozen: the repo dir (preserves today's dev/venv behaviour exactly).
- `env_file_path()` → `os.path.join(app_support_dir(), ".env")`
- `bundled_resource(name)` → `os.path.join(sys._MEIPASS, name)` for bundled templates.
- `ensure_env_seeded()` → on first frozen launch, create the app-support dir and seed
  `.env` by copying (in priority order): the existing dev `~/whisper-dictate/.env`
  (auto-migrate the owner's current setup — paths, API key, toggles carry over), else
  the bundled `.env.example`. Idempotent; best-effort (swallows OSErrors).

### 2. Wire `app_paths` into `dictate.py`

Replace `dictate.py:24-27` (the module-level `load_dotenv`):

```python
from dotenv import load_dotenv
from app_paths import env_file_path, ensure_env_seeded
ensure_env_seeded()
load_dotenv(env_file_path())
```

This runs at import time, including in each spawn child (which re-imports `dictate.py`)
— fine: the resolver returns the same stable path. All existing `os.environ.get` /
`_env_int` / `LIVE_SETTINGS` reads below are unchanged. Dev behaviour is identical
(`env_file_path()` returns the repo `.env` when not frozen).

### 3. Wire `app_paths` into `menubar_app.py`

Route every `.env` path lookup through `app_paths.env_file_path()`:
- `menubar_app.py:155` — `self._env_path = app_paths.env_file_path()` (was
  `os.path.join(repo_dir, ".env")`). Live toggle write-back (`persist_env_setting`)
  and "Edit .env" then target the writable app-support file.
- `menubar_app.py:45-57` (`ensure_env_file`) — seed from bundled `.env.example` via
  `app_paths.bundled_resource('.env.example')` when frozen.
- `menubar_app.py:398-401` (`_on_log` fallback) — the primary `log_path`
  (`~/whisper-dictate.log`, passed from `dictate.py:1186`) already resolves correctly
  when frozen; the `repo_dir`-relative fallback only matters in dev, so it stays.

`repo_dir` (line 433) remains computed for dev-path fallbacks; it's harmless inside the
bundle.

### 4. New `whisper_dictate.spec` — PyInstaller onedir config

- **Entry:** `Analysis(['dictate.py'], pathex=['.'])`
- **excludes:** `faster_whisper`, `ctranslate2`, `pynvnl`/`pynvml`, `win11toast`,
  `pystray`, `PIL`/`Pillow`, `winsound`, `tray_app` — Windows-only / CUDA / lazy and
  not installed in the macOS venv; excludes suppress analysis warnings and shrink the
  bundle. (`faster_whisper_backend` itself is safe — heavy imports are lazy.)
- **datas:** `[('.env.example', '.')]` — bundled as the first-launch seed template.
  **Never** bundle the real `.env` (it holds the owner's API key).
- **hiddenimports:** `rumps`, `AppKit`, `Cocoa`, `objc`, `Foundation`, `Quartz`,
  `ApplicationServices`, `CoreText`, `sounddevice`, `_sounddevice`, `pyperclip`,
  `pynput.keyboard._darwin`, `pynput._util.darwin`, `numpy`. (PyInstaller's hooks cover
  most; the first build will reveal any still-missing — see Risks.)
- **EXE:** `name='WhisperDictate'`, `console=False`.
- **BUNDLE:** `name='Whisper Dictate.app'`, `bundle_identifier='com.mortalcornflake.whisper-dictate'`,
  and an `info_plist` dict:
  - `LSUIElement: True` — menu-bar accessory, no Dock icon (required; none exists today).
  - `CFBundleName` / `CFBundleDisplayName`: "Whisper Dictate".
  - `CFBundleShortVersionString: "1.0.0"`, `CFBundleVersion: "1"`.
  - `NSMicrophoneUsageDescription` — mic TCC prompt text.
  - `NSAppleEventsUsageDescription` — the app shells out to `osascript … tell
    application "System Events" to keystroke`; a bundled app may be asked to grant
    Automation control of System Events, so this description should be present.

### 5. New `build-macos-app.sh`

Activates the venv, `pip install pyinstaller` if missing,
`pyinstaller --noconfirm whisper_dictate.spec`, then
`codesign --deep --force -s - "dist/Whisper Dictate.app"` (ad-hoc), and prints the
TCC grants the owner must give + the suggested install command
(`cp -R "dist/Whisper Dictate.app" /Applications/`). Single-instance, idempotent.

### 6. Repo housekeeping

- `requirements-dev.txt`: add `pyinstaller>=6.0`.
- `.gitignore`: add `build/`, `dist/`. (Keep `whisper_string.spec` tracked — it's the
  build source of truth.)
- `README.md`: add a "Run as a macOS app" install path (build → /Applications → grant
  permissions → optional Login Item). Leave the venv/Terminal path as the dev default.
- `CLAUDE.md`: add a section clarifying the PyInstaller `.app` is the durable fix for
  the reboot/TCC thread (distinct from the abandoned LaunchAgent wrapper), update the
  "OPEN THREAD" note, and record the new `.env` location + bundle ID.

---

## Files

| Action | Path | Change |
|---|---|---|
| new | `app_paths.py` | frozen-aware `.env`/resource resolver + seed/migrate |
| new | `whisper_dictate.spec` | PyInstaller onedir config + Info.plist |
| new | `build-macos-app.sh` | build + ad-hoc sign + install guidance |
| edit | `dictate.py` | `load_dotenv` block (~L24-27) → use `app_paths` |
| edit | `menubar_app.py` | `self._env_path` (L155), `ensure_env_file` (L45-57), log fallback (L398-401) → `app_paths` |
| edit | `requirements-dev.txt` | + `pyinstaller>=6.0` |
| edit | `.gitignore` | + `build/`, `dist/` |
| edit | `README.md`, `CLAUDE.md` | document the `.app` build + durable-autostart story |

Reused as-is: `multiprocessing.freeze_support()` (already first line of `__main__`,
`dictate.py:1208`), `set_start_method('spawn')` (`dictate.py:1075`), the lazy
`run_with_menubar` import (`dictate.py:1170`), the TCC-triggering paths
(pynput `keyboard.Listener`, osascript paste via `platform_io/darwin.py`, sounddevice
`InputStream`), and all whisper.cpp subprocess + model-path resolution (stays external).

---

## Known risks (the first build will iterate — this is normal)

1. **pyobjc + PyInstaller** is the likeliest source of hidden-import misses; expect 2–3
   build/fix cycles. `--collect-all` fallback available if hidden-import listing isn't enough.
2. **sounddevice's PortAudio dylib** should be picked up by PyInstaller's hook; verify at runtime.
3. **multiprocessing spawn child in a frozen onedir app** — `freeze_support()` is already
   correctly placed; verify the recorder actually captures audio (this exercises it).
4. **Automation TCC** — `osascript` driving System Events from a bundled app may prompt
   for Automation permission; the owner grants it once. Mitigated by `NSAppleEventsUsageDescription`.
5. **Re-grant after a rebuild** — ad-hoc signing's `cdhash` changes per build, so a TCC
   re-grant *may* be needed after each rebuild during dev sessions. This does **not**
   affect the owner's daily use (the binary is unchanged across OS updates, which is the
   actual durability win). A stable self-signed certificate is an optional follow-up if
   rebuild-regrant becomes annoying.

---

## Verification

1. `./build-macos-app.sh` builds `dist/Whisper Dictate.app` with no analysis errors.
2. `open "dist/Whisper Dictate.app"` → 🎙 menu-bar icon appears; no Dock icon (LSUIElement).
3. Grant **Input Monitoring**, **Accessibility**, **Microphone** (and Automation if
   prompted) to "Whisper Dictate" in System Settings → Privacy & Security.
4. Tap the hotkey → record → release → confirm a **local** transcription (whisper.cpp)
   is captured in the spawn child and pasted — proves `freeze_support` + onedir work.
5. Toggle a Sounds/Pasting checkbox → confirm it writes to
   `~/Library/Application Support/WhisperDictate/.env` and survives a quit+relaunch.
6. Confirm `~/whisper-dictate/.env` was migrated on first launch (API key + paths present).
7. `pytest` still green (dev path unchanged — `app_paths` returns repo dir when not frozen).
8. **Owner reboot test (the real goal, deferred to owner):** with the `.app` set as a
   Login Item, confirm it auto-starts and the hotkey works after a reboot.

---

## Out of scope (follow-ups)

- Custom `.icns` icon (only shows in Spotlight/Launchpad for an LSUIElement app).
- Stable self-signed cert (no re-grant on rebuild).
- Notarization (only needed if distributing to others).
- **Flipping the Login Item from `start-dictate.sh` to the `.app`** — the payoff for
  durable auto-start, but best done as a final step after the owner confirms the `.app`
  works and grants stick.
