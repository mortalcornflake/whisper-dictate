# Whisper Dictate

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/macOS-Sonoma%20%7C%20Sequoia-black.svg)](https://www.apple.com/macos/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org)

> Fast, accurate voice-to-text dictation for macOS. Hold a key, speak, release to transcribe and paste anywhere.

<!--
TODO: Add demo GIF here
![Demo](assets/demo.gif)
-->

## Why Whisper Dictate?

macOS's built-in dictation is... fine. But if you want:

- **No API keys needed** - Works out of the box, 100% local
- **Completely private** - Your voice never leaves your Mac
- **Works offline** - No internet required after setup
- **Better accuracy** - Uses OpenAI's Whisper Large v3 Turbo model
- **Actually free** - Runs on your hardware, no subscriptions or usage limits
- **No training** - Works great out of the box, no "learning your voice"
- **Technical terms** - Excellent accuracy on code, APIs, technical jargon

### How it compares

| Solution | Model | Speed | Cost | Setup |
|----------|-------|-------|------|-------|
| **Whisper Dictate (local)** | Large v3 Turbo | ~3-5s | Free | Clone + install.sh |
| Whisper Dictate (Groq cloud) | Large v3 | ~2s | Free | API key (optional upgrade) |
| OpenAI Whisper API | Large v3 | ~3-5s | $0.006/min | API key + payment |
| Local Whisper (CLI) | Base/Small | 5-15s | Free | Download 141-466MB |
| macOS Dictation | Apple | ~2s | Free | Built-in (less accurate) |

Then Whisper Dictate is for you.

## Quick Start

### Step 1: Download

**Option A: If you have git** (most developers)
```bash
git clone https://github.com/mortalcornflake/whisper-dictate.git
cd whisper-dictate
```

**Option B: No git? Download directly**
1. Go to [https://github.com/mortalcornflake/whisper-dictate](https://github.com/mortalcornflake/whisper-dictate)
2. Click the green **"< > Code"** button
3. Click **"Download ZIP"**
4. Unzip the file
5. Open Terminal and navigate to the folder:
   ```bash
   cd ~/Downloads/whisper-dictate-main
   ```

### Step 2: Install

```bash
./install.sh
```

The installer will:
1. Check Python is installed (install from [python.org](https://www.python.org) if needed)
2. Set up Python environment and dependencies
3. **Build whisper.cpp and download the V3 Turbo model** (the core transcription engine)
4. Guide you through macOS permissions
5. Optionally set up a Groq API key for cloud-accelerated transcription
6. Optionally set up auto-start

**That's it — no accounts, no API keys, no sign-ups.** Just clone, install, and start dictating.

## Manual Installation

<details>
<summary>Click to expand manual steps</summary>

### 1. Clone and setup

```bash
git clone https://github.com/mortalcornflake/whisper-dictate.git
cd whisper-dictate

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install whisper.cpp (local transcription engine)

```bash
git clone https://github.com/ggerganov/whisper.cpp ~/whisper.cpp
cd ~/whisper.cpp
cmake -B build
cmake --build build

# Download the V3 Turbo model (best accuracy, 1.5GB)
cd models
./download-ggml-model.sh large-v3-turbo
```

### 3. Configure

```bash
cp .env.example .env
# That's it — local mode is the default, no API keys needed
```

### 4. Grant macOS permissions

**Accessibility** (required for keyboard monitoring):
1. System Settings > Privacy & Security > Accessibility
2. Click + and add Terminal.app
3. Toggle ON

**Microphone** (required for recording):
1. System Settings > Privacy & Security > Microphone
2. Toggle ON when prompted on first run

### 5. Run it

```bash
source venv/bin/activate && python dictate.py
# Or run in background:
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &
```

</details>

## Usage

| Action | Result |
|--------|--------|
| **Press Right Option** | Start recording (you'll hear a "Tink") |
| **Release Right Option** | Stop, transcribe, and paste (you'll hear "Blow" then "Glass") |
| **Press Right Option again** | Also stops recording (works if release event is lost) |
| **Ctrl+Shift+R** | Reset if stuck recording (you'll hear "Glass" and see notification) |
| **`~/whisper-dictate/force-reset.sh`** | Force reset from another terminal (if keyboard shortcuts not working) |

**Audio cues explained:**
- **"Tink"** = Recording started
- **"Blow"** = Recording stopped, transcribing...
- **"Glass"** = Done! Clipboard restored and safe to paste

That's it. The transcribed text is automatically pasted wherever your cursor is.

**Note:** If you get stuck recording (macOS can lose key release events during heavy terminal output), just tap the Right Option key again to stop.

## Configuration

All settings can be configured via environment variables in `.env`:

```bash
# Local transcription is the default — no API keys needed!
# The installer configures whisper.cpp paths automatically.

# Optional: Change hotkey (default: alt_r = Right Option)
# HOTKEY=alt_r  # Options: alt_r, alt_l, ctrl_r, ctrl_l, cmd_r, cmd_l, f5, f6, f7, f8, f9, f10

# Optional: Preserve clipboard after pasting (default: true)
# PRESERVE_CLIPBOARD=false  # Set to false for faster pasting (no 0.5s delay)

# Optional: Auto-press Enter/Return after pasting (default: false)
# AUTO_PRESS_ENTER=true  # Automatically press Enter after transcription

# Optional: Auto-stop timeout in seconds (default: 300)
# AUTO_STOP_TIMEOUT=300  # Auto-stop and transcribe after 5 min (warning sound at 10s before)

# Optional: Pin to specific microphone
# INPUT_DEVICE=MacBook Pro Microphone
```

### Changing the microphone

By default, it uses your system's default input device. This works for most setups.

**Want to dictate while listening to music on AirPods?** Pin to your built-in mic so audio output stays on AirPods while recording uses the laptop mic:

```bash
# Add to your .env file:
INPUT_DEVICE=MacBook Pro Microphone
```

To find your microphone name, run:
```bash
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

Common device names: `MacBook Pro Microphone`, `iMac Microphone`, `USB Microphone`

## Want Even Faster Results? (Optional)

Local transcription takes ~3-5 seconds on Apple Silicon. If you want ~2 second turnaround, you can optionally add cloud transcription via Groq's free API:

1. Get a free API key at [console.groq.com](https://console.groq.com)
2. Add to your `.env`:
   ```bash
   GROQ_API_KEY=gsk_your_key_here
   DICTATE_BACKEND=groq
   ```

**Groq free tier limits** (more than enough for personal use):

| Limit | Amount |
|-------|--------|
| Requests/minute | 20 |
| Requests/day | 2,000 |
| Audio/hour | 7,200 sec (2 hrs) |
| Audio/day | 28,800 sec (8 hrs) |

When using Groq, the app automatically falls back to local transcription if the API is unreachable (offline, rate limited, etc).

You can also use OpenAI's API (`DICTATE_BACKEND=openai`) but it's paid ($0.006/min).

## Local Transcription Details

### Server Mode (automatic)

When you use local transcription, the app automatically manages a whisper server for fast response:

1. **First transcription**: Starts whisper-server in background (~5-10sec to load model)
2. **Subsequent transcriptions**: Uses existing server (instant)
3. **Auto-cleanup**: Shuts down server after 30 min idle (frees 1.5GB RAM)

See [SERVER_MODE.md](SERVER_MODE.md) for detailed architecture and all failure scenarios.

### Model options

The installer lets you choose your model:

- **large-v3-turbo** (default): Best accuracy, ~3-5s transcription, 1.5GB download
- **small.en**: Good balance, ~2-3s transcription, 466MB
- **base.en**: Fast but less accurate on technical terms, 141MB

Apple Silicon Macs (M1/M2/M3/M4) handle the large-v3-turbo model easily — it's the recommended choice.

## Auto-start on Login

**Recommended: Login Items** (most reliable)

```bash
# Add the startup script to Login Items via command line:
osascript -e 'tell application "System Events" to make login item at end with properties {path:"'$HOME'/whisper-dictate/start-dictate.sh", hidden:true}'
```

Or manually: System Settings > General > Login Items > click + > select `~/whisper-dictate/start-dictate.sh`

**Alternative: Shell profile**

Add to `~/.zshrc` or `~/.bash_profile`:

```bash
# Auto-start Whisper Dictate
if ! pgrep -f "dictate.py" > /dev/null; then
    cd ~/whisper-dictate && source venv/bin/activate && \
    nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &
fi
```

**Manual restart:**
```bash
~/whisper-dictate/restart-dictate.sh
```

## Quick Troubleshooting

### Is it running?
```bash
pgrep -fl dictate
```
If you see output with "dictate.py", it's running. If not:
```bash
cd ~/whisper-dictate
source venv/bin/activate
python dictate.py
```

### Stuck recording?
**Just tap the Right Option key again** - this will stop the recording immediately.

If that doesn't work, try these in order:
1. **Ctrl+Shift+R** - keyboard reset
2. **`~/whisper-dictate/force-reset.sh`** - signal-based reset (doesn't kill the process)
3. **`~/whisper-dictate/restart-dictate.sh`** - full restart (kills process and orphaned subprocesses, then restarts)

### How do I restart it?
```bash
~/whisper-dictate/restart-dictate.sh
```

### Not recording / no dictation?
1. Check Terminal has **Microphone** permission (System Settings > Privacy & Security > Microphone)
2. Check Terminal has **Accessibility** permission (System Settings > Privacy & Security > Accessibility)

### Where are the logs?
```bash
tail -f ~/whisper-dictate.log
```

---

## Detailed Troubleshooting

<details>
<summary><b>"This process is not trusted"</b></summary>

Accessibility permission not granted. Add Terminal.app to:
System Settings > Privacy & Security > Accessibility

</details>

<details>
<summary><b>No sound / not recording</b></summary>

Microphone permission not granted. Check:
System Settings > Privacy & Security > Microphone

</details>

<details>
<summary><b>Hotkey not working / Stuck recording</b></summary>

If stuck in recording mode, try these in order:
1. **Tap the hotkey again** (Right Option) - toggle mode will stop it
2. **Ctrl+Shift+R** - keyboard-based reset
3. **`~/whisper-dictate/force-reset.sh`** - external reset via signals (doesn't kill the process)
4. **Wait for auto-stop** - automatic safety reset kicks in after 5 min (configurable via `AUTO_STOP_TIMEOUT`)
5. **`~/whisper-dictate/restart-dictate.sh`** - full restart (kills and restarts the process)

Other issues:
- Check the app is running: `pgrep -fl dictate`
- Check for conflicts with system shortcuts (Siri uses F5, Dictation uses Fn Fn)
- Try a different hotkey

**Common cause:** Switching windows or notifications while holding the hotkey can lose the key release event.

</details>

<details>
<summary><b>Non-US keyboard / special characters not working</b></summary>

The default Right Option key is used for special characters on many non-US keyboard layouts (e.g., `Right Option + e` = `é`). If this conflicts with your typing, change to a different hotkey in your `.env`:

```bash
HOTKEY=ctrl_r  # Right Control instead
# Or use a function key: f6, f7, f8, etc.
```

</details>


<details>
<summary><b>Weird/wrong language transcription</b></summary>

Recording was too short or mostly silence. Hold the key longer and speak clearly.

</details>

<details>
<summary><b>Slow transcription</b></summary>

- Local: The first transcription after startup takes ~5-10s (loading model). Subsequent ones are ~3-5s.
- Cloud: Check internet connection (~100ms latency needed)
- Try a smaller model (`small.en` instead of `large-v3-turbo`) for faster local speed

</details>

<details>
<summary><b>View logs</b></summary>

```bash
tail -f ~/whisper-dictate.log
```

Check if running:
```bash
pgrep -fl dictate
```

Restart if needed:
```bash
~/whisper-dictate/restart-dictate.sh
```

</details>

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features:
- Menu bar UI with recording status indicator
- Language selection (Whisper supports 99 languages)
- LLM transcript cleanup (remove filler words, fix punctuation)
- Context-aware formatting per app
- Voice commands
- Snippet expansion

## Contributing

PRs welcome! Please open an issue first to discuss major changes.

## Questions & Feedback

- **Issues/Bugs**: [Open a GitHub issue](https://github.com/mortalcornflake/whisper-dictate/issues)
- **Questions**: [@mortalcornflake on X](https://x.com/mortalcornflake)

## Support

If you find this useful:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Development-ff5f5f?logo=ko-fi)](https://ko-fi.com/mortalcornflake)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsor-ea4aaa?logo=github)](https://github.com/sponsors/mortalcornflake)

## License

MIT - see [LICENSE](LICENSE)

## Built By

[Modicum Studio](https://modicum.studio) — built because every dictation tool was either slow, inaccurate, or expensive. Open source because progress shouldn't be locked behind a paywall.

## Acknowledgments

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) for excellent local inference
- [Groq](https://groq.com) for the optional cloud-accelerated Whisper API
- [pynput](https://github.com/moses-palmer/pynput) for cross-platform keyboard monitoring
