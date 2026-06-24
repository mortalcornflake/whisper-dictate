"""macOS platform integration (afplay, osascript, SIGUSR1)."""
import signal
import subprocess

# Semantic event -> macOS system sound name (in /System/Library/Sounds).
_SOUNDS = {
    "start": "Tink",     # recording started (short, non-intrusive)
    "stop": "Blow",      # recording stopped
    "done": "Glass",     # transcription pasted / reset complete
    "warning": "Sosumi", # approaching auto-stop limit
}


def play_sound(event, blocking=False):
    """Play a system sound for a semantic event ('start'/'stop'/'done'/'warning')."""
    name = _SOUNDS.get(event, "Glass")
    cmd = ["afplay", f"/System/Library/Sounds/{name}.aiff"]
    if blocking:
        subprocess.run(cmd, capture_output=True)
    else:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title, message):
    """Show a macOS notification."""
    # Escape backslashes and double quotes for AppleScript string literals.
    safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
    safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
    subprocess.run([
        "osascript", "-e",
        f'display notification "{safe_message}" with title "{safe_title}"'
    ], capture_output=True)


def send_paste():
    """Simulate Cmd+V (more reliable than pyautogui on macOS)."""
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to keystroke "v" using command down'
    ])


def send_enter():
    """Simulate the Return key (key code 36)."""
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to key code 36'
    ])


def register_external_reset(callback):
    """Register an external reset trigger. On macOS this is SIGUSR1, which
    force-reset.sh sends."""
    def handler(signum, frame):
        callback()
    signal.signal(signal.SIGUSR1, handler)
