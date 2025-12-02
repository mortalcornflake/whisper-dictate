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
  - **2024-12-02 FIX #1:** More aggressive termination (FAILED):
    - Added `is_resetting` flag to block new recordings during reset
    - Changed `stream.stop()` to `stream.abort()` for immediate termination
    - Added explicit frames buffer clear
    - **Result:** STILL DIDN'T WORK - stream kept recording

  - **2024-12-02 FIX #2:** NUCLEAR OPTION (TESTING NOW):
    - Don't try to stop/abort/close the stream at all
    - Just set `recorder.stream = None` and abandon it
    - Create completely fresh Recorder immediately
    - Attempt to kill old stream in background thread (but don't wait)
    - If background kill fails, we don't care - stream is leaked but we've moved on
    - This makes reset instant and non-blocking

**Hypothesis:**
- The stream can't be reliably stopped from keyboard listener thread
- Threading issue: callback thread doesn't see flag updates in time
- Trying to stop the stream blocks or fails silently
- **New approach:** Just abandon the stream and create new one - nuclear but effective

**Status:** 🧪 TESTING NOW - User stuck and needs to try Ctrl+Shift+R

**If this doesn't work:**
- User's suggestion: separate background script monitoring for reset hotkey
- That script would `pkill -9 dictate.py && restart` when hotkey detected
- Bypasses all threading/stream issues entirely

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
