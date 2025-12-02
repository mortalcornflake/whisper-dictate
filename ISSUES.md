# Known Issues

## Active Issues

### CRITICAL: Ctrl+Shift+R reset doesn't actually stop recording

**Status:** Active bug, needs investigation
**Priority:** High - only workaround is kill/restart process

**Symptoms:**
- Ctrl+Shift+R combo IS detected (plays Glass sound and shows notification)
- But recording does NOT actually stop
- Microphone stays active, keeps recording
- Only fix: kill process and restart

**What we know:**
- `reset()` function IS being called (confirmed by sound + notification)
- Sound plays = code reaches `sound("Glass")` at end of reset()
- But `self.recorder.stream.stop()` and `self.recorder.recording = False` aren't working
- Attempted fixes so far:
  - Improved key detection logic (didn't help)
  - Added `self.recorder.recording = False` before stream.stop() (didn't help)
  - Added exception handling (didn't help)
  - **2024-12-02 FIX:** More aggressive termination (NEEDS TESTING):
    - Added `is_resetting` flag to block new recordings during reset
    - Changed `stream.stop()` to `stream.abort()` for immediate termination
    - Added explicit frames buffer clear
    - Added 0.1s delay for stream thread termination
    - Prevented hotkey from starting recording if `is_resetting=True`

**Hypothesis:**
- Stream.stop() is too graceful - audio callback thread keeps running
- stream.abort() should forcefully terminate immediately
- Race condition: new recording could start before reset completes

**Status:** 🧪 TESTING - User needs to try Ctrl+Shift+R when stuck and report back

**If this doesn't work:**
- Consider full listener restart instead of just recorder reset
- May need to investigate sounddevice internals or switch audio library
- Could add a "nuclear" reset that recreates the entire DictationListener

---

## Resolved Issues

### ✅ Clipboard gets overwritten
**Fixed:** Implemented clipboard preservation (optional via PRESERVE_CLIPBOARD env var)

### ✅ urllib3 SSL warning cluttering logs
**Fixed:** Added warning filter

### ✅ Hotkey hardcoded in code
**Fixed:** Made configurable via HOTKEY env var

### ✅ App bundle permissions issues
**Fixed:** Removed app bundle, documented Terminal-only approach
