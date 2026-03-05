# Known Issues

## Active Issues

None! All known issues have been resolved.

---

## Resolved Issues

### ✅ Stuck recording (key release lost)
**Problem:** macOS occasionally drops the key release event during heavy terminal output, leaving the recorder stuck.
**Fix:** Toggle mode — press the hotkey again to stop recording. Auto-stop safety net kicks in after 5 minutes as a backup.

### ✅ Clipboard gets overwritten
**Fix:** Clipboard preservation — your clipboard is automatically saved and restored after pasting. Optional via `PRESERVE_CLIPBOARD` env var.

### ✅ Hotkey hardcoded in code
**Fix:** Configurable via `HOTKEY` env var in `.env`.

### ✅ App bundle permissions issues
**Fix:** Runs via Terminal directly (no app bundle needed).
