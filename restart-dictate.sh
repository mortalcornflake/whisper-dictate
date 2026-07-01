#!/bin/bash
# Restart Whisper Dictate - use this if it gets stuck recording.
# Waits for the old instance to actually exit before starting a new one, so we
# never end up with two copies running (which would double-type / double-paste).

echo "Stopping dictate.py..."
pkill -f "[Pp]ython.*dictate.py"

# Wait (up to ~10s) for the old process to fully exit — its SIGTERM cleanup
# (whisper-server shutdown, subprocess joins) can take a couple of seconds. If it
# refuses to die, force-kill it so we don't start a second overlapping instance.
for _ in $(seq 1 20); do
    pgrep -f "[Pp]ython.*dictate.py" > /dev/null || break
    sleep 0.5
done
if pgrep -f "[Pp]ython.*dictate.py" > /dev/null; then
    echo "Old instance didn't exit — force-killing..."
    pkill -9 -f "[Pp]ython.*dictate.py"
    sleep 1
fi

# Kill any orphaned multiprocessing children (standby recorders) and stray server
pkill -f "multiprocessing.spawn"
pkill -f "whisper-server"
sleep 0.5

echo "Starting dictate.py..."
cd ~/whisper-dictate || exit 1
source venv/bin/activate
nohup python dictate.py >> ~/whisper-dictate.log 2>&1 &

sleep 2

count=$(pgrep -f "[Pp]ython.*dictate.py" | wc -l | tr -d ' ')
if [ "$count" = "1" ]; then
    echo "✅ Whisper Dictate restarted successfully"
elif [ "$count" = "0" ]; then
    echo "❌ Failed to restart - check ~/whisper-dictate.log"
else
    echo "⚠️  $count instances running - run this script again or pkill -9 -f dictate.py"
fi
