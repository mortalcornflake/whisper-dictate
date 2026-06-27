"""Windows platform integration (winsound, toast notifications, pynput paste).

Mirrors the interface in ``darwin.py`` so the cross-platform core in
``dictate.py`` stays unchanged. See CROSS_PLATFORM.md (Phase 3).
"""
import threading
import winsound

from pynput.keyboard import Controller, Key

# Semantic event -> Windows system sound alias (played via winsound.PlaySound).
# These are built-in Windows sounds, so nothing has to be bundled. They're chosen
# to be audibly distinct rather than to match the macOS sounds exactly.
_SOUNDS = {
    "start": "SystemAsterisk",    # recording started
    "stop": "SystemExclamation",  # recording stopped
    "done": "SystemDefault",      # transcription pasted / reset complete
    "warning": "SystemHand",      # approaching auto-stop limit
}

_keyboard = Controller()


def play_sound(event, blocking=False):
    """Play a Windows system sound for a semantic event
    ('start'/'stop'/'done'/'warning')."""
    alias = _SOUNDS.get(event, "SystemDefault")
    # Synchronous is winsound's default; add SND_ASYNC only when non-blocking.
    flags = winsound.SND_ALIAS
    if not blocking:
        flags |= winsound.SND_ASYNC
    try:
        winsound.PlaySound(alias, flags)
    except RuntimeError:
        # If the alias can't be played for any reason, fall back to a plain beep.
        winsound.MessageBeep(winsound.MB_OK)


def notify(title, message):
    """Show a Windows toast notification (best-effort, non-blocking).

    Uses win11toast if it's installed; if it's missing or errors, we skip the
    toast rather than crash dictation over a cosmetic notification."""
    def _show():
        try:
            from win11toast import toast
            toast(str(title), str(message))
        except Exception:
            pass
    threading.Thread(target=_show, daemon=True).start()


def send_paste():
    """Simulate Ctrl+V."""
    with _keyboard.pressed(Key.ctrl):
        _keyboard.press("v")
        _keyboard.release("v")


def send_enter():
    """Simulate the Enter key."""
    _keyboard.press(Key.enter)
    _keyboard.release(Key.enter)


def register_external_reset(callback):
    """No external signal on Windows (no SIGUSR1); the tray menu triggers resets
    instead. Kept as a no-op so the shared core can call it unconditionally."""
    pass
