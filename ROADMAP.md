# Whisper Dictate - Future Roadmap

## Current State (v1)
- Local-first: runs entirely on your Mac using whisper.cpp (no API keys needed)
- Default model: Large v3 Turbo (best accuracy, ~3-5s on Apple Silicon)
- Configurable hotkey via .env (default: Right Option key)
- Optional cloud transcription via Groq API (free, ~2s turnaround)
- Automatic fallback to local if cloud is unreachable
- Sound feedback (Tink/Blow/Glass)
- Clipboard preservation (your clipboard is restored after pasting)
- Toggle mode: press hotkey to start, press again to stop
- Ctrl+Shift+R manual reset + auto-stop safety net
- Server mode: whisper server stays in background for fast response, auto-shuts down after 30min idle

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

Libraries: `rumps` or `pyobjc` AppKit (full control)

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

## Completed Features

- [x] Local-first defaults (no API key needed out of the box)
- [x] Clipboard preservation (PRESERVE_CLIPBOARD env var)
- [x] Configurable hotkey via .env (HOTKEY env var)
- [x] Toggle mode (press again to stop — fixes lost key release events)
- [x] Auto-stop safety timeout (configurable via AUTO_STOP_TIMEOUT)
- [x] Server mode with auto-cleanup (30min idle timeout)

## Technical Debt

- [ ] Better error handling for malformed audio
- [ ] Configurable sounds (or disable)
- [ ] Config file instead of env vars
- [ ] Proper logging to file with rotation
- [ ] PID file tracking to kill orphaned whisper-server on next start
