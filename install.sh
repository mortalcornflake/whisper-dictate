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
echo -e "${BLUE}║     Fast, Free Voice-to-Text          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check for Python 3
echo -e "${YELLOW}[1/6] Checking requirements...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo "Install it from https://www.python.org or via Homebrew: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo -e "${YELLOW}[2/6] Setting up Python environment...${NC}"
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
echo -e "${YELLOW}[3/6] Configuring API key...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env

    echo ""
    echo -e "${BLUE}You need a FREE Groq API key for cloud transcription.${NC}"
    echo -e "1. Visit: ${GREEN}https://console.groq.com${NC}"
    echo -e "2. Sign up (free)"
    echo -e "3. Go to API Keys section"
    echo -e "4. Create a new key and copy it"
    echo ""
    read -p "Paste your Groq API key here (or press Enter to add later): " GROQ_KEY

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
        echo -e "     Just replace ${BLUE}gsk_your_key_here${NC} with your actual key"
    fi
else
    echo -e "  ${GREEN}✓${NC} .env file already exists"
fi

# macOS permissions reminder
echo ""
echo -e "${YELLOW}[4/6] macOS Permissions Setup...${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: You must grant two permissions:${NC}"
echo ""
echo -e "1. ${GREEN}Accessibility${NC} (for detecting the hotkey)"
echo "   System Settings > Privacy & Security > Accessibility"
echo -e "   ${BLUE}Add Terminal.app and toggle it ON${NC}"
echo ""
echo -e "2. ${GREEN}Microphone${NC} (for recording audio)"
echo "   System Settings > Privacy & Security > Microphone"
echo -e "   ${BLUE}Toggle Terminal.app ON (will prompt on first use)${NC}"
echo ""

read -p "Open System Settings now? (Y/n): " OPEN_SETTINGS
if [[ ! "$OPEN_SETTINGS" =~ ^[Nn]$ ]]; then
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    echo -e "  ${GREEN}✓${NC} System Settings opened"
    echo ""
    read -p "Press Enter after you've added Terminal to Accessibility..."
fi

# Auto-start setup
echo ""
echo -e "${YELLOW}[5/6] Auto-start on login setup...${NC}"
read -p "Start Whisper Dictate automatically when you open Terminal? (Y/n): " AUTOSTART

if [[ ! "$AUTOSTART" =~ ^[Nn]$ ]]; then
    # Detect shell
    if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
        PROFILE="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
        PROFILE="$HOME/.bash_profile"
    else
        PROFILE="$HOME/.zshrc"  # Default to zsh on modern macOS
    fi

    # Check if already added
    if grep -q "whisper-dictate" "$PROFILE" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Auto-start already configured in $PROFILE"
    else
        cat >> "$PROFILE" << 'EOF'

# Auto-start Whisper Dictate
if ! pgrep -f "dictate.py" > /dev/null; then
    cd ~/whisper-dictate && source venv/bin/activate && \
    nohup python dictate.py >> ~/whisper-dictate.log 2>&1 & \
    echo "🎤 Whisper Dictate started in background"
fi
EOF
        echo -e "  ${GREEN}✓${NC} Added auto-start to $PROFILE"
        echo -e "     ${BLUE}It will start automatically in new Terminal windows${NC}"
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipped - you'll need to start it manually"
fi

# Test run
echo ""
echo -e "${YELLOW}[6/6] Starting Whisper Dictate...${NC}"

# Kill any existing instance
pkill -f "dictate.py" 2>/dev/null || true
sleep 1

# Start it
source venv/bin/activate
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &
PID=$!

echo -e "  ${GREEN}✓${NC} Started (PID: $PID)"
echo ""

# Wait a moment and check if it's still running
sleep 2
if kill -0 $PID 2>/dev/null; then
    echo -e "${GREEN}✓ Running successfully!${NC}"
    echo ""
    echo "You should see a notification: \"Whisper Dictate Ready!\""
else
    echo -e "${RED}✗ Failed to start${NC}"
    echo "Check logs: tail ~/whisper-dictate.log"
    echo ""
fi

# Done!
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Installation Complete! 🎉        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}How to use:${NC}"
echo "  1. Hold Right Option key"
echo "  2. Speak your text"
echo "  3. Release Right Option"
echo "  → Text appears where your cursor is!"
echo ""
echo -e "${BLUE}If you get stuck recording:${NC}"
echo "  • Just tap Right Option again to stop"
echo "  • Or press Ctrl+Shift+R to reset"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  Check if running:  pgrep -fl dictate"
echo "  View logs:         tail -f ~/whisper-dictate.log"
echo "  Restart:           ~/whisper-dictate/restart-dictate.sh"
echo ""
echo -e "${YELLOW}Questions or issues?${NC}"
echo "  GitHub: https://github.com/mortalcornflake/whisper-dictate/issues"
echo "  X/Twitter: @mortalcornflake"
echo ""
