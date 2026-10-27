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

### Menu Bar UI — DONE (Jun 2026)
Built as `menubar_app.py` using `rumps`, the macOS counterpart to the Windows
tray (`tray_app.py`). Owns the main thread while the keyboard listener runs in a
background thread. Shows recording state (mic / red-dot / paused glyph in the
bar), a live recording timer, a last-transcription preview + copy action,
Pause/Resume listening, Reset, and quick access to settings (`.env`) and the log.
Enabled by default on macOS; set `MENU_BAR=false` to run headless. Falls back to
headless automatically if `rumps` isn't installed.

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

### Evaluating new speech engines (where to look, how to judge)
Whisper large-v3-turbo through whisper.cpp stays the default until something beats it on the text people actually
want, not just on speed. Speech models move fast, so check these every few months or when a notable release lands:

**Where new options show up**
- Hugging Face Open ASR Leaderboard (`hf-audio/open_asr_leaderboard`): word error and speed across open models
  (English and multilingual). A first filter only: it scores normalised text, which hides the formatting and
  vocabulary differences that decide dictation.
- whisper.cpp releases (github.com/ggml-org/whisper.cpp): new Whisper builds, quantisations, and the optional
  Core ML encoder (runs Whisper's encoder on the Neural Engine).
- WhisperKit (github.com/argmaxinc/WhisperKit): Whisper compiled for Core ML / the Neural Engine. The route to
  Whisper's text with the Neural Engine's efficiency, if that matters.
- FluidAudio (github.com/FluidInference/FluidAudio) and its Hugging Face org (`FluidInference`): Core ML ports for
  the Neural Engine. Already includes Parakeet v2 (English), v3, Ultra and Phonon-2 retrains, Canary-1B-v2, a
  vocabulary booster and a number normaliser (inverse text normalisation).
- NVIDIA NeMo model cards on Hugging Face (`nvidia/parakeet-*`, `nvidia/canary-*`), and Apple's MLX community
  ports (`mlx-community`).

**How to judge a candidate (what the Oct 2026 test taught)**
1. Run it over a set of real dictations from the person who'll use it, not a public benchmark: the 2026 test used
   302 of the author's own recordings.
2. Automatic scores need two references from different model families (e.g. a Whisper model and a non-Whisper
   one); each family scores the other worse, so on their own they can't pick a winner.
3. The decider is a blind side-by-side: 20 short clips where the two engines differ, sides shuffled, the user
   picks the closer text. Decide the threshold first (15 of 20 for a one-sided sign test).
4. Time it like for like (cold call vs cold call, warm vs warm) with the GPU otherwise idle, and report the
   slowest 5%, not the average.
5. Check formatting separately (numbers as digits, capitals, punctuation, filler words): normal scoring strips it.
6. Measure energy per dictation on battery before claiming a battery benefit.

### Parakeet on the Neural Engine as a battery option (tested Oct 2026, not the default)
A second Mac-only backend: NVIDIA Parakeet TDT 0.6B v3 through FluidAudio (Core ML, int8 encoder on the Apple
Neural Engine), with Whisper kept as the default everywhere.

**What a test on 302 real dictations found (27 Oct 2026):**
- Much faster: the slowest 5% of dictations under 30 s took 0.5 s against 1.5 s for the warm Whisper server
  (large-v3-turbo); 0.8 s against 6.8 s across all lengths. It runs off the GPU, so it doesn't compete with other
  GPU work.
- Text: in 20 blind side-by-side pairs, Whisper's was preferred every time. Parakeet is more literal (keeps
  stutters, "uh"/"um", "gonna", spells numbers out: "one oh nine") and misses technical words Whisper gets
  (SD card, OpenRAW, eSIM). Its vocabulary boosting made things worse with a long list.
- Power use: not yet measured (the test machine was plugged in).

**Possible future shape:** a backend setting (`DICTATE_BACKEND=parakeet`), and optionally switching by power
source: Parakeet on battery, Whisper on mains. Before building it: measure energy per dictation on battery for
both; add number normalising (FluidAudio ships one) and a filler/stutter filter, then re-check the text blind.

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
- [x] macOS menu bar app (`menubar_app.py`, rumps) — Jun 2026
- [x] Windows tray app (`tray_app.py`, pystray)

## Technical Debt

- [ ] Better error handling for malformed audio
- [ ] Configurable sounds (or disable)
- [ ] Config file instead of env vars
- [ ] Proper logging to file with rotation
- [ ] PID file tracking to kill orphaned whisper-server on next start
