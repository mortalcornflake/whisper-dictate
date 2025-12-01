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

- **Better accuracy** - Whisper consistently outperforms Apple's dictation
- **Faster results** - ~2 second turnaround via Groq's LPU-accelerated API
- **Actually free** - Groq's free tier gives you 8 hours of audio/day (vs OpenAI's $0.006/min)
- **No model download** - Cloud-based, so no 500MB-3GB model to install
- **Works offline** - Automatic fallback to local whisper.cpp when needed
- **No training** - Works great out of the box, no "learning your voice"
- **Privacy option** - Run 100% locally if you prefer

### How it compares

| Solution | Speed | Cost | Setup |
|----------|-------|------|-------|
| **Whisper Dictate (Groq)** | ~2s | Free | Just an API key |
| OpenAI Whisper API | ~3-5s | $0.006/min | API key + payment |
| Local Whisper | 5-15s | Free | Download 500MB-3GB model |
| macOS Dictation | ~2s | Free | Built-in (but less accurate) |

Then Whisper Dictate is for you.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/mortalcornflake/whisper-dictate.git
cd whisper-dictate

# Run the installer
./install.sh
```

The installer will:
1. Set up Python environment
2. Install dependencies
3. Configure your API key
4. Optionally set up auto-start
5. Guide you through macOS permissions

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
2. Click + and add `WhisperDictate.app` (or Terminal)
3. Toggle ON

**Microphone** (required for recording):
1. System Settings > Privacy & Security > Microphone
2. Toggle ON when prompted on first run

### 4. Run it

```bash
open WhisperDictate.app
# Or: source venv/bin/activate && python dictate.py
```

</details>

## Usage

| Action | Result |
|--------|--------|
| **Hold Right Option** | Start recording (you'll hear a "Pop") |
| **Release Right Option** | Stop, transcribe, and paste (you'll hear "Blow" then "Glass") |

That's it. The transcribed text is automatically pasted wherever your cursor is.

## Configuration

All settings can be configured via environment variables in `.env`:

```bash
# Required: Groq API key (free at console.groq.com)
GROQ_API_KEY=gsk_your_key_here

# Optional: Use OpenAI instead of Groq
# OPENAI_API_KEY=sk-your_key_here
# DICTATE_BACKEND=openai

# Optional: Local whisper.cpp for offline fallback
# WHISPER_CPP_PATH=~/whisper.cpp/build/bin/whisper-cli
# WHISPER_MODEL_PATH=~/whisper.cpp/models/ggml-base.en.bin
```

### Changing the hotkey

Edit `dictate.py` and change `HOTKEY_KEY`:

```python
# Options:
HOTKEY_KEY = keyboard.Key.alt_r      # Right Option (default)
HOTKEY_KEY = keyboard.Key.alt_l      # Left Option
HOTKEY_KEY = keyboard.Key.ctrl_r     # Right Control
HOTKEY_KEY = keyboard.Key.f6         # F6
```

### Changing the microphone

By default, it uses "MacBook Pro Microphone" so you can listen to music on AirPods while dictating. To use system default:

```python
INPUT_DEVICE = None  # Use system default input
```

## Offline Mode with whisper.cpp

For fully local transcription (slower but private):

```bash
# Install whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make

# Download a model
./models/download-ggml-model.sh base.en

# Add to your .env
WHISPER_CPP_PATH=~/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=~/whisper.cpp/models/ggml-base.en.bin

# Optional: Use local-only mode
DICTATE_BACKEND=local
```

## Auto-start on Login

The installer can set this up, or manually:

```bash
# Create LaunchAgent
cat > ~/Library/LaunchAgents/com.whisper-dictate.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisper-dictate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>/path/to/whisper-dictate/WhisperDictate.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

# Load it
launchctl load ~/Library/LaunchAgents/com.whisper-dictate.plist
```

## Troubleshooting

<details>
<summary><b>"This process is not trusted"</b></summary>

Accessibility permission not granted. Add Python.app or WhisperDictate.app to:
System Settings > Privacy & Security > Accessibility

</details>

<details>
<summary><b>No sound / not recording</b></summary>

Microphone permission not granted. Check:
System Settings > Privacy & Security > Microphone

</details>

<details>
<summary><b>Hotkey not working</b></summary>

- Check the app is running: `ps aux | grep dictate`
- Check for conflicts with system shortcuts (Siri uses F5, Dictation uses Fn Fn)
- Try a different hotkey

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
tail -f ~/whisper-dictate/dictate.log
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
- LLM transcript cleanup (remove filler words, fix punctuation)
- Context-aware formatting per app
- Menu bar UI
- Voice commands
- Snippet expansion

## Contributing

PRs welcome! Please open an issue first to discuss major changes.

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
