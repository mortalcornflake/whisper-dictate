"""Windows system-tray app for Whisper Dictate (Phase 3).

Shows a tray icon (grey = idle, red = recording) with a right-click menu
(Reset / Settings / Quit). Windows-only; the macOS build keeps running the
keyboard listener on the main thread without a tray. The tray's Reset replaces
the SIGUSR1-based external reset, which doesn't exist on Windows.
"""
import os
import threading

import pystray
from PIL import Image, ImageDraw

_IDLE_COLOR = (120, 120, 120)  # grey
_REC_COLOR = (220, 40, 40)     # red


def _make_icon(color):
    """Draw a simple circular status icon in the given RGB colour."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return img


# Pre-render both states so the poll loop just swaps between them.
_ICONS = {False: _make_icon(_IDLE_COLOR), True: _make_icon(_REC_COLOR)}


def _open_settings():
    """Open the .env settings file in the default editor, creating it from the
    example template the first time."""
    repo = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(repo, ".env")
    if not os.path.exists(env_path):
        example = os.path.join(repo, ".env.example")
        try:
            if os.path.exists(example):
                import shutil
                shutil.copyfile(example, env_path)
        except OSError:
            pass
    try:
        os.startfile(env_path)  # Windows-only
    except OSError:
        pass


def run_with_tray(listener):
    """Run the keyboard listener (background thread) plus the tray icon (this
    thread). Blocks until the user chooses Quit, then returns so the caller can
    clean up."""
    listener.start_listening()

    icon = pystray.Icon("whisper-dictate", _ICONS[False], "Whisper Dictate")

    def on_reset(icon_, item):
        listener.reset(reason="Tray menu reset")

    def on_settings(icon_, item):
        _open_settings()

    def on_quit(icon_, item):
        listener.stop_listening()
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("Reset", on_reset),
        pystray.MenuItem("Settings", on_settings),
        pystray.MenuItem("Quit", on_quit),
    )

    # Reflect recording state in the icon. Polling keeps the tray decoupled from
    # the listener's threading rather than having callbacks touch the icon.
    stop_poll = threading.Event()

    def poll_status():
        last = None
        while not stop_poll.wait(0.3):
            state = bool(listener.is_recording)
            if state != last:
                icon.icon = _ICONS[state]
                icon.title = ("Whisper Dictate - Recording" if state
                              else "Whisper Dictate")
                last = state

    threading.Thread(target=poll_status, daemon=True).start()
    icon.run()  # blocks until icon.stop()
    stop_poll.set()
