#!/bin/bash
# Start Whisper Dictate at login (added to Login Items)

# Wait a moment for system to settle after login
sleep 3

# Check if already running
if pgrep -f "[Pp]ython.*dictate.py" > /dev/null; then
    echo "Whisper Dictate already running"
    exit 0
fi

cd ~/whisper-dictate
source venv/bin/activate
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &
