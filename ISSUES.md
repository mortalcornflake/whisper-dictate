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

**Hypothesis:**
- Stream callback may be ignoring the `recording = False` flag
- Race condition between reset() and audio callback thread
- Stream.stop() may not be synchronous on macOS
- Need to investigate sounddevice stream lifecycle

**Next steps:**
- Add more aggressive stream termination
- Try stream.abort() instead of stream.close()
- Add flag to completely prevent new recordings after reset
- Consider recreating the entire listener, not just recorder

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
