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

- **Better accuracy** - Uses OpenAI's Whisper Large v3 (the best Whisper model)
- **Faster results** - ~2 second turnaround via Groq's LPU-accelerated API
- **Actually free** - Groq's free tier gives you 8 hours of audio/day (vs OpenAI's $0.006/min)
- **Smart fallback** - Automatically switches to local when offline (persistent server mode)
- **No training** - Works great out of the box, no "learning your voice"
- **Privacy option** - Run 100% locally if you prefer
- **Technical terms** - Excellent accuracy on code, APIs, technical jargon

### How it compares

| Solution | Model | Speed | Cost | Setup |
|----------|-------|-------|------|-------|
| **Whisper Dictate (Groq)** | Large v3 | ~2s | Free | Just an API key |
| OpenAI Whisper API | Large v3 | ~3-5s | $0.006/min | API key + payment |
| Local Whisper (server) | Large v3 Turbo | ~3-5s | Free | Download 1.5GB model |
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
2. Set up Python environment
3. Install dependencies
4. Help you get a FREE Groq API key
5. Guide you through macOS permissions
6. **Optionally install whisper.cpp for local fallback** (clones, builds, downloads model)
7. Optionally set up auto-start

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

### 2. Configure API key

Get a free API key from [console.groq.com](https://console.groq.com), then:

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Grant macOS permissions

**Accessibility** (required for keyboard monitoring):
1. System Settings > Privacy & Security > Accessibility
2. Click + and add Terminal.app
3. Toggle ON

**Microphone** (required for recording):
1. System Settings > Privacy & Security > Microphone
2. Toggle ON when prompted on first run

### 4. Run it

```bash
source venv/bin/activate && python dictate.py
# Or run in background:
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &
```

</details>

## Usage

| Action | Result |
|--------|--------|
| **Press Right Option** | Start recording (you'll hear a "Pop") |
| **Release Right Option** | Stop, transcribe, and paste (you'll hear "Blow" then "Glass") |
| **Press Right Option again** | Also stops recording (works if release event is lost) |
| **Ctrl+Shift+R** | Reset if stuck recording (you'll hear "Glass" and see notification) |
| **`~/whisper-dictate/force-reset.sh`** | Force reset from another terminal (if keyboard shortcuts not working) |

**Audio cues explained:**
- **"Pop"** = Recording started
- **"Blow"** = Recording stopped, transcribing...
- **"Glass"** = Done! Clipboard restored and safe to paste

That's it. The transcribed text is automatically pasted wherever your cursor is.

**Note:** If you get stuck recording (macOS can lose key release events during heavy terminal output), just tap the Right Option key again to stop.

## Configuration

All settings can be configured via environment variables in `.env`:

```bash
# Required: Groq API key (free at console.groq.com)
GROQ_API_KEY=gsk_your_key_here

# Optional: Change hotkey (default: alt_r = Right Option)
# HOTKEY=alt_r  # Options: alt_r, alt_l, ctrl_r, ctrl_l, cmd_r, cmd_l, f5, f6, f7, f8, f9, f10

# Optional: Preserve clipboard after pasting (default: true)
# PRESERVE_CLIPBOARD=false  # Set to false for faster pasting (no 0.5s delay)

# Optional: Auto-press Enter/Return after pasting (default: false)
# AUTO_PRESS_ENTER=true  # Automatically press Enter after transcription

# Optional: Auto-stop timeout in seconds (default: 45)
# AUTO_STOP_TIMEOUT=45  # Auto-stop and transcribe stuck recordings after 45s

# Optional: Use OpenAI instead of Groq
# OPENAI_API_KEY=sk-your_key_here
# DICTATE_BACKEND=openai

# Optional: Enable/disable local fallback (default: true)
# Set to false if you don't have whisper.cpp installed
# FALLBACK_TO_LOCAL=true

# Optional: Local whisper.cpp paths (configured automatically by installer)
# WHISPER_CPP_PATH=~/whisper.cpp/build/bin/whisper-cli
# WHISPER_SERVER_PATH=~/whisper.cpp/build/bin/whisper-server
# WHISPER_MODEL_PATH=~/whisper.cpp/models/ggml-large-v3-turbo.bin
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

## Offline Mode with whisper.cpp

**Recommended: Use the installer** - it handles everything automatically:
```bash
./install.sh
# When prompted "Install local fallback support?", answer Y
# Choose model: 1=base.en (fast), 2=small.en (balanced), 3=large-v3-turbo (best)
```

**Manual setup** (if you prefer):

```bash
# Install whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build
cmake --build build

# Download a model (choose based on speed vs accuracy)
cd models
./download-ggml-model.sh base.en        # Fast (141MB)
./download-ggml-model.sh small.en       # Balanced (466MB)
./download-ggml-model.sh large-v3-turbo # Best accuracy (1.5GB)

# Add to your .env
FALLBACK_TO_LOCAL=true
WHISPER_CPP_PATH=~/whisper.cpp/build/bin/whisper-cli
WHISPER_SERVER_PATH=~/whisper.cpp/build/bin/whisper-server
WHISPER_MODEL_PATH=~/whisper.cpp/models/ggml-large-v3-turbo.bin

# Optional: Use local-only mode (no cloud API)
DICTATE_BACKEND=local
```

### Local Fallback with Server Mode

When Groq fails (no WiFi, rate limited, VPN blocking), the app automatically:
1. **First fallback**: Starts whisper-server in background (~5-10sec to load model)
2. **Subsequent fallbacks**: Uses existing server (instant transcription)
3. **Auto-cleanup**: Shuts down server after 30 min idle (frees 1.5GB RAM)

See [SERVER_MODE.md](SERVER_MODE.md) for detailed architecture and all failure scenarios.

**Model recommendations:**
- **large-v3-turbo**: Best accuracy, ~3-5s transcription (recommended)
- **small.en**: Good balance, ~2-3s transcription
- **base.en**: Fast but less accurate on technical terms

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
3. **`~/whisper-dictate/restart-dictate.sh`** - full restart (kills and restarts)

### How do I restart it?
```bash
~/whisper-dictate/restart-dictate.sh
```

### Not recording / no dictation?
1. Check Terminal has **Microphone** permission (System Settings > Privacy & Security > Microphone)
2. Check Terminal has **Accessibility** permission (System Settings > Privacy & Security > Accessibility)
3. Make sure you added your Groq API key to `.env`

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
4. **Wait 45 seconds** - automatic safety reset kicks in (configurable via `AUTO_STOP_TIMEOUT`)
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

- Cloud: Check internet connection (~100ms latency needed)
- Local: Use a smaller model (`base.en` instead of `large`)

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

## Groq Free Tier Limits

| Limit | Amount |
|-------|--------|
| Requests/minute | 20 |
| Requests/day | 2,000 |
| Audio/hour | 7,200 sec (2 hrs) |
| Audio/day | 28,800 sec (8 hrs) |

More than enough for personal dictation.

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

## Acknowledgments

- [Groq](https://groq.com) for the blazing fast, free Whisper API
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) for excellent local inference
- [pynput](https://github.com/moses-palmer/pynput) for cross-platform keyboard monitoring
