#!/bin/bash
# Start Whisper Dictate at login (added to System Settings > General > Login Items).
# Logs a heartbeat each login so you can confirm from the log whether it fired
# after a reboot (the usual "did it auto-start?" question).

LOG="$HOME/whisper-dictate.log"
stamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(stamp)] start-dictate.sh: login launch" >> "$LOG"

# Wait a moment for the system to settle after login
sleep 3

# Self-heal: if a copy is already running, do nothing (avoids double-typing)
if pgrep -f "[Pp]ython.*dictate.py" > /dev/null; then
    echo "[$(stamp)] start-dictate.sh: already running — nothing to do" >> "$LOG"
    exit 0
fi

cd "$HOME/whisper-dictate" || { echo "[$(stamp)] start-dictate.sh: repo dir missing" >> "$LOG"; exit 1; }
source venv/bin/activate
echo "[$(stamp)] start-dictate.sh: launching dictate.py via $(command -v python)" >> "$LOG"
nohup python dictate.py >> "$LOG" 2>&1 &
echo "[$(stamp)] start-dictate.sh: launched (pid $!)" >> "$LOG"
