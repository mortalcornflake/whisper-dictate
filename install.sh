#!/bin/bash
#
# Whisper Dictate - Installation Script
# https://github.com/mortalcornflake/whisper-dictate
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Whisper Dictate Installer       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check for Python 3
echo -e "${YELLOW}Checking requirements...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo "Install it from https://www.python.org or via Homebrew: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo -e "${YELLOW}Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "  ${GREEN}✓${NC} Created virtual environment"
else
    echo -e "  ${GREEN}✓${NC} Virtual environment exists"
fi

# Activate and install dependencies
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "  ${GREEN}✓${NC} Installed dependencies"

# Setup .env file
echo ""
echo -e "${YELLOW}Configuring API key...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env

    echo ""
    echo -e "${BLUE}You need a Groq API key for cloud transcription (free tier available).${NC}"
    echo -e "Get one at: ${GREEN}https://console.groq.com${NC}"
    echo ""
    read -p "Enter your Groq API key (or press Enter to skip): " GROQ_KEY

    if [ -n "$GROQ_KEY" ]; then
        # Use sed to replace the placeholder
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/gsk_your_key_here/$GROQ_KEY/" .env
        else
            sed -i "s/gsk_your_key_here/$GROQ_KEY/" .env
        fi
        echo -e "  ${GREEN}✓${NC} API key saved to .env"
    else
        echo -e "  ${YELLOW}!${NC} Skipped - you can add it later by editing .env"
    fi
else
    echo -e "  ${GREEN}✓${NC} .env file already exists"
fi

# Optional: Setup local whisper.cpp
echo ""
echo -e "${YELLOW}Local whisper.cpp fallback (optional)...${NC}"
echo "This allows offline transcription when cloud is unavailable."
echo ""
read -p "Do you have whisper.cpp installed? (y/N): " HAS_WHISPER

if [[ "$HAS_WHISPER" =~ ^[Yy]$ ]]; then
    read -p "Path to whisper-cli binary: " WHISPER_PATH
    read -p "Path to model file (.bin): " MODEL_PATH

    if [ -n "$WHISPER_PATH" ] && [ -n "$MODEL_PATH" ]; then
        echo "" >> .env
        echo "WHISPER_CPP_PATH=$WHISPER_PATH" >> .env
        echo "WHISPER_MODEL_PATH=$MODEL_PATH" >> .env
        echo -e "  ${GREEN}✓${NC} Whisper.cpp paths saved"
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipped - cloud-only mode (install whisper.cpp later for offline support)"
fi

# Setup auto-start (optional)
echo ""
echo -e "${YELLOW}Auto-start on login (optional)...${NC}"
read -p "Start Whisper Dictate automatically on login? (y/N): " AUTOSTART

if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
    PLIST_PATH="$HOME/Library/LaunchAgents/com.whisper-dictate.plist"
    APP_PATH="$SCRIPT_DIR/WhisperDictate.app"

    cat > "$PLIST_PATH" << EOF
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
        <string>$APP_PATH</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

    launchctl load "$PLIST_PATH" 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} LaunchAgent installed"
else
    echo -e "  ${YELLOW}!${NC} Skipped - run manually with: open WhisperDictate.app"
fi

# macOS permissions reminder
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         macOS Permissions             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: You must grant two permissions for the app to work:${NC}"
echo ""
echo -e "1. ${GREEN}Accessibility${NC} (for keyboard monitoring)"
echo "   System Settings > Privacy & Security > Accessibility"
echo "   Add: WhisperDictate.app (or Terminal if running from command line)"
echo ""
echo -e "2. ${GREEN}Microphone${NC} (for audio recording)"
echo "   System Settings > Privacy & Security > Microphone"
echo "   Toggle ON when prompted"
echo ""

read -p "Open System Settings now? (Y/n): " OPEN_SETTINGS
if [[ ! "$OPEN_SETTINGS" =~ ^[Nn]$ ]]; then
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
fi

# Done!
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Installation Complete!        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo "To start Whisper Dictate:"
echo -e "  ${BLUE}open WhisperDictate.app${NC}"
echo ""
echo "Usage:"
echo "  Hold Right Option key → speak → release to transcribe and paste"
echo ""
echo "Logs: tail -f dictate.log"
echo ""
echo -e "${YELLOW}If you find this useful, consider supporting development:${NC}"
echo -e "  ${GREEN}https://ko-fi.com/mortalcornflake${NC}"
echo ""
