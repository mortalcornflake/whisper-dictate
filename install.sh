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
echo -e "${BLUE}║   Private, Local Voice-to-Text        ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check for Python 3
echo -e "${YELLOW}[1/7] Checking requirements...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo "Install it from https://www.python.org or via Homebrew: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo -e "${YELLOW}[2/7] Setting up Python environment...${NC}"
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

# Local whisper.cpp setup (core transcription engine)
echo ""
echo -e "${YELLOW}[3/7] Setting up local transcription engine...${NC}"
echo ""
echo -e "${BLUE}Whisper Dictate uses whisper.cpp to transcribe your voice locally on your Mac.${NC}"
echo "No internet or API keys needed — everything runs on your hardware."
echo ""

WHISPER_DIR="$HOME/whisper.cpp"

# Check if whisper.cpp already exists
if [ -d "$WHISPER_DIR" ]; then
    echo -e "  ${GREEN}✓${NC} whisper.cpp already exists at $WHISPER_DIR"

    # Check if it's built
    if [ ! -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
        echo -e "  ${YELLOW}!${NC} Not built yet, building now..."
        cd "$WHISPER_DIR"
        if cmake -B build > /dev/null 2>&1 && cmake --build build --config Release -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4) 2>&1 | tail -5; then
            echo -e "  ${GREEN}✓${NC} Built whisper.cpp"
        else
            echo -e "  ${RED}✗${NC} Build failed"
            echo "  Try building manually: cd $WHISPER_DIR && cmake -B build && cmake --build build"
            echo -e "  ${YELLOW}!${NC} Continuing without local engine (will need cloud API)..."
        fi
        cd "$SCRIPT_DIR"
    fi
else
    echo -e "  ${BLUE}→${NC} Cloning whisper.cpp..."
    git clone https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR" > /dev/null 2>&1
    echo -e "  ${GREEN}✓${NC} Cloned whisper.cpp"

    echo -e "  ${BLUE}→${NC} Building whisper.cpp (this may take 1-2 minutes)..."
    cd "$WHISPER_DIR"
    if cmake -B build > /dev/null 2>&1 && cmake --build build --config Release -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4) 2>&1 | tail -5; then
        echo -e "  ${GREEN}✓${NC} Built whisper.cpp"
    else
        echo -e "  ${RED}✗${NC} Build failed"
        echo "  Try building manually: cd $WHISPER_DIR && cmake -B build && cmake --build build"
        echo -e "  ${YELLOW}!${NC} Continuing without local engine (will need cloud API)..."
    fi
    cd "$SCRIPT_DIR"
fi

# Model selection
echo ""
echo -e "${BLUE}Choose a transcription model:${NC}"
echo "  1) base.en       - Fast, less accurate (141MB, ~1-2s)"
echo "  2) small.en      - Balanced (466MB, ~2-3s)"
echo "  3) large-v3-turbo - Best accuracy (1.5GB, ~3-5s) [RECOMMENDED]"
echo ""
read -p "Enter choice (1/2/3) [3]: " MODEL_CHOICE
MODEL_CHOICE=${MODEL_CHOICE:-3}

case $MODEL_CHOICE in
    1)
        MODEL_NAME="base.en"
        MODEL_FILE="ggml-base.en.bin"
        ;;
    2)
        MODEL_NAME="small.en"
        MODEL_FILE="ggml-small.en.bin"
        ;;
    *)
        MODEL_NAME="large-v3-turbo"
        MODEL_FILE="ggml-large-v3-turbo.bin"
        ;;
esac

# Download model if not exists
if [ -f "$WHISPER_DIR/models/$MODEL_FILE" ]; then
    echo -e "  ${GREEN}✓${NC} Model $MODEL_NAME already downloaded"
else
    echo -e "  ${BLUE}→${NC} Downloading $MODEL_NAME model..."
    cd "$WHISPER_DIR/models"
    ./download-ggml-model.sh "$MODEL_NAME" > /dev/null 2>&1
    cd "$SCRIPT_DIR"
    echo -e "  ${GREEN}✓${NC} Downloaded $MODEL_NAME model"
fi

# Setup .env file with local defaults
echo ""
echo -e "${YELLOW}[4/7] Configuring settings...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}✓${NC} Created .env from template"
else
    echo -e "  ${GREEN}✓${NC} .env file already exists"
fi

# Update .env with whisper.cpp paths
echo -e "  ${BLUE}→${NC} Configuring local transcription paths..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|# WHISPER_CPP_PATH=.*|WHISPER_CPP_PATH=$WHISPER_DIR/build/bin/whisper-cli|" .env
    sed -i '' "s|# WHISPER_SERVER_PATH=.*|WHISPER_SERVER_PATH=$WHISPER_DIR/build/bin/whisper-server|" .env
    sed -i '' "s|# WHISPER_MODEL_PATH=.*|WHISPER_MODEL_PATH=$WHISPER_DIR/models/$MODEL_FILE|" .env
    sed -i '' "s|# FALLBACK_TO_LOCAL=.*|FALLBACK_TO_LOCAL=true|" .env
else
    sed -i "s|# WHISPER_CPP_PATH=.*|WHISPER_CPP_PATH=$WHISPER_DIR/build/bin/whisper-cli|" .env
    sed -i "s|# WHISPER_SERVER_PATH=.*|WHISPER_SERVER_PATH=$WHISPER_DIR/build/bin/whisper-server|" .env
    sed -i "s|# WHISPER_MODEL_PATH=.*|WHISPER_MODEL_PATH=$WHISPER_DIR/models/$MODEL_FILE|" .env
    sed -i "s|# FALLBACK_TO_LOCAL=.*|FALLBACK_TO_LOCAL=true|" .env
fi
echo -e "  ${GREEN}✓${NC} Local transcription configured"

# macOS permissions reminder
echo ""
echo -e "${YELLOW}[5/7] macOS Permissions Setup...${NC}"
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

# Optional cloud API setup
echo ""
echo -e "${YELLOW}[6/7] Cloud Transcription (optional)...${NC}"
echo ""
echo -e "${BLUE}Want even faster transcription? (~2s instead of ~3-5s)${NC}"
echo "You can optionally add a FREE Groq API key for cloud-accelerated transcription."
echo "This is completely optional — local mode works great on its own."
echo ""
read -p "Set up Groq cloud transcription? (y/N): " SETUP_GROQ

if [[ "$SETUP_GROQ" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "1. Visit: ${GREEN}https://console.groq.com${NC}"
    echo -e "2. Sign up (free)"
    echo -e "3. Go to API Keys section"
    echo -e "4. Create a new key and copy it"
    echo ""
    read -p "Paste your Groq API key here (or press Enter to skip): " GROQ_KEY

    if [ -n "$GROQ_KEY" ]; then
        # Use sed to replace the placeholder (| delimiter avoids issues with special chars in key)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|# GROQ_API_KEY=gsk_your_key_here|GROQ_API_KEY=$GROQ_KEY|" .env
            sed -i '' "s|# DICTATE_BACKEND=local|DICTATE_BACKEND=groq|" .env
        else
            sed -i "s|# GROQ_API_KEY=gsk_your_key_here|GROQ_API_KEY=$GROQ_KEY|" .env
            sed -i "s|# DICTATE_BACKEND=local|DICTATE_BACKEND=groq|" .env
        fi
        echo -e "  ${GREEN}✓${NC} Groq API key saved — using cloud transcription with local fallback"
    else
        echo -e "  ${YELLOW}!${NC} Skipped — using local transcription"
    fi
else
    echo -e "  ${GREEN}✓${NC} Using local transcription (no cloud API)"
fi

# Auto-start setup
echo ""
echo -e "${YELLOW}[7/7] Auto-start on login setup...${NC}"
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
    (cd ~/whisper-dictate && ./venv/bin/python dictate.py >> ~/whisper-dictate.log 2>&1 &)
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
echo -e "${YELLOW}Starting Whisper Dictate...${NC}"

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
