#!/bin/bash
# Restart Whisper Dictate - use this if it gets stuck recording

echo "Stopping dictate.py..."
pkill -f "[Pp]ython.*dictate.py"
sleep 1
# Kill any orphaned multiprocessing children (standby recorders)
pkill -f "multiprocessing.spawn"
sleep 0.5

echo "Starting dictate.py..."
cd ~/whisper-dictate
source venv/bin/activate
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &

sleep 2

if pgrep -f "[Pp]ython.*dictate.py" > /dev/null; then
    echo "✅ Whisper Dictate restarted successfully"
else
    echo "❌ Failed to restart - check ~/whisper-dictate.log"
fi
