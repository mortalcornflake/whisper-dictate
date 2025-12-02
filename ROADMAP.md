# Whisper Dictate - Future Roadmap

## Current State (v1)
- Configurable hotkey via .env (default: Right Option key)
- Transcribe via Groq Whisper API (fast, free tier)
- Automatic fallback to local whisper.cpp if offline/rate-limited
- Sound feedback (Pop/Blow/Glass)
- Clipboard preservation (your clipboard is restored after pasting)
- Ctrl+Shift+R manual reset + 5-minute auto-reset safety net
- Manual startup via Terminal (permissions work reliably)

---

## Future Feature: LLM Transcript Cleanup

### Why
Raw transcription includes filler words (um, uh, like, you know), false starts, and sometimes awkward phrasing. Running through an LLM can clean this up before pasting.

### Implementation Plan

1. **Add cleanup toggle** in config:
   ```python
   CLEANUP_ENABLED = True
   CLEANUP_MODEL = "llama-3.1-8b-instant"  # Fast, good enough
   ```

2. **Add cleanup function**:
   ```python
   def cleanup_transcript(text: str) -> str:
       response = requests.post(
           "https://api.groq.com/openai/v1/chat/completions",
           headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
           json={
               "model": CLEANUP_MODEL,
               "messages": [{
                   "role": "system",
                   "content": "Clean up this transcript. Remove filler words, fix grammar, keep meaning. Output only the cleaned text."
               }, {
                   "role": "user",
                   "content": text
               }],
               "temperature": 0.3
           }
       )
       return response.json()["choices"][0]["message"]["content"]
   ```

3. **Insert into flow** (in `_process_audio`):
   ```python
   text = transcribe(audio_bytes)
   if text and CLEANUP_ENABLED:
       text = cleanup_transcript(text)
   if text:
       paste_text(text)
   ```

4. **Fallback to Ollama** if Groq rate-limited:
   ```python
   def cleanup_transcript_local(text: str) -> str:
       response = requests.post(
           "http://localhost:11434/api/generate",
           json={"model": "llama3.2:3b", "prompt": f"Clean up: {text}", "stream": False}
       )
       return response.json()["response"]
   ```

### Latency Impact
- Current: ~2s (transcribe only)
- With cleanup: ~3s (transcribe + LLM)
- Acceptable for most use cases

### Rate Limit Considerations
- Groq free tier: 30 RPM, 6K TPM for Llama 3.1 8B
- Each cleanup ~100-500 tokens, so plenty of headroom
- Could share rate limit tracking between whisper + LLM calls

---

## Other Future Ideas

### ✅ Clipboard Preservation (COMPLETED)
~~Save clipboard contents before pasting, restore after~~

**Status**: Implemented in dictate.py
- Added `get_clipboard()` and `set_clipboard()` helper functions
- Modified `paste_text()` to save/restore clipboard contents
- Your clipboard is now preserved after dictation
- Made optional via `PRESERVE_CLIPBOARD` env var (default: true)
- Disable for faster pasting with no 0.5s delay

### ✅ Configurable Hotkey via .env (COMPLETED)
~~Allow hotkey configuration without editing code~~

**Status**: Implemented in dictate.py
- Added `parse_hotkey()` function to parse env var to pynput key
- Supports: alt_r, alt_l, ctrl_r, ctrl_l, cmd_r, cmd_l, f5-f10, and more
- Configure via `HOTKEY=` in `.env` - no code editing needed

### Language Selection
Whisper supports 99 languages. Add language hint for better accuracy:
```bash
# .env
WHISPER_LANGUAGE=en  # or es, fr, de, ja, etc.
```

Pass to API:
```python
data={"model": "whisper-large-v3", "language": WHISPER_LANGUAGE}
```

### Context-Aware Formatting
Detect active app and adjust output:
- **Slack/Discord**: casual, lowercase
- **Email/Docs**: proper punctuation, formal
- **Terminal**: exact transcription, no cleanup
- **Code editors**: format as comments

```python
from AppKit import NSWorkspace

def get_active_app():
    return NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
```

### Menu Bar UI
Replace background process with proper menu bar app:
- Show recording status
- Toggle cleanup on/off
- See recent transcriptions
- Quick access to settings

Libraries: `rumps` (simple) or `pyobjc` AppKit (full control)

### Voice Commands
Prefix phrases that trigger actions:
- "Computer, search for..." → open browser search
- "Computer, open..." → launch app
- "Computer, type..." → just transcribe

### Snippet Expansion
Define voice shortcuts:
- "Insert my email" → pastes email address
- "Insert signature" → pastes signature block
- "Insert meeting link" → pastes Zoom/Meet link

Store in `~/.whisper-dictate/snippets.json`

### Push-to-Talk vs Voice Activity Detection
Option to auto-detect speech start/stop instead of holding key:
- Use `webrtcvad` for voice activity detection
- Start recording on voice, stop after 1s silence
- More hands-free, but trickier to get right

---

## Technical Debt
- [x] Suppress urllib3 SSL warning properly
- [x] Improve Ctrl+Shift+R reset reliability (stops recorder.recording flag)
- [x] Add auto-reset safety timeout (5 minutes)
- [x] Move imports to top of file (code cleanup)
- [x] Configurable hotkey via .env
- [ ] Better error handling for malformed audio
- [ ] Configurable sounds (or disable)
- [ ] Config file instead of env vars
- [ ] Proper logging to file with rotation
