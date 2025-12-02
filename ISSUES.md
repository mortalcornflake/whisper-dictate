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

**ROOT CAUSE DISCOVERED (2024-12-02):**
- Happens during LONG dictations (30+ seconds)
- Occurs when Claude Code session is actively outputting to terminal
- Terminal is scrolling/updating heavily while user holds hotkey
- **Theory:** macOS drops the key RELEASE event when terminal is busy
- pynput never receives the release event
- Recorder waits forever for a release that never comes
- Reset doesn't help because the recorder is "working correctly" - it just never got the stop signal

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

**BETTER SOLUTIONS (now that we know the root cause):**

Since the issue is LOST KEY RELEASE EVENTS, not broken recorder:

1. **Auto-stop after max recording time** (EASY FIX):
   - Current auto-reset is 5 minutes (way too long)
   - Add separate MAX_RECORDING_LENGTH = 60 seconds
   - Auto-stop recording after 60s even without key release
   - Prevents getting stuck on long dictations

2. **Double-tap to stop** (ALTERNATE APPROACH):
   - If hotkey pressed AGAIN while recording, stop instead of ignoring
   - Toggle mode: press to start, press again to stop
   - Works around lost release events entirely
   - More reliable than waiting for release event

3. **Periodic key state check**:
   - Every 1 second, check if hotkey is physically still pressed
   - If recording but key is no longer down, auto-stop
   - Would catch lost release events quickly
   - Not sure if pynput can query current key state though

**Recommendation:** Try option #1 (auto-stop at 60s) - simplest fix

**IMPLEMENTED (2024-12-02):**
- ✅ Added auto-stop at 60 seconds
- Background thread checks every 5 seconds
- If recording > 60s, auto-stops and processes audio normally
- Shows notification: "Auto-stopped after Xs"
- Nuclear reset still exists at 5 minutes as backup
- **This should prevent 90% of stuck recording issues**

**Status:** 🧪 Deployed - waiting for user to test during next long dictation

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
