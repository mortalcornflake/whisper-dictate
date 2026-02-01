#!/bin/bash
# Force reset Whisper Dictate if stuck recording
# Sends SIGUSR1 to trigger reset WITHOUT killing the process

echo "🔥 Force resetting Whisper Dictate..."

# Find the dictate.py process
PID=$(pgrep -f "dictate.py")

if [ -z "$PID" ]; then
    echo "❌ dictate.py is not running"
    exit 1
fi

echo "Found dictate.py process: $PID"

# Send SIGUSR1 to trigger reset handler
echo "Sending SIGUSR1 reset signal..."
kill -USR1 $PID

echo ""
echo "✅ Reset signal sent!"
echo "Check ~/whisper-dictate.log to verify reset occurred"
echo ""
echo "If still stuck, use: ~/whisper-dictate/restart-dictate.sh"
