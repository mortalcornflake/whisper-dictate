#!/bin/bash
# Force reset Whisper Dictate if stuck recording
# This tries to reset WITHOUT killing the process

echo "🔥 Force resetting Whisper Dictate..."

# Find the dictate.py process
PID=$(pgrep -f "dictate.py")

if [ -z "$PID" ]; then
    echo "❌ dictate.py is not running"
    exit 1
fi

echo "Found dictate.py process: $PID"
echo ""
echo "Trying reset methods..."
echo ""

# Method 1: Send SIGUSR1 signal
echo "1. Sending SIGUSR1 signal..."
kill -USR1 $PID
sleep 1

# Method 2: Delete trigger file
echo "2. Deleting reset trigger file..."
rm -f ~/.whisper-dictate-reset
sleep 1

echo ""
echo "✅ Reset signals sent!"
echo "Check ~/whisper-dictate.log to verify reset occurred"
echo ""
echo "If still stuck, use: ~/whisper-dictate/restart-dictate.sh"
