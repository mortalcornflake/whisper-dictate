"""Windows platform integration.

Implemented in Phase 3 (see CROSS_PLATFORM.md). This module is importable so the
package loads cleanly, but the functions raise until Phase 3 lands.

Planned implementation:
- play_sound: winsound.PlaySound with bundled .wav files (mapped from the
  semantic events 'start'/'stop'/'done'/'warning').
- notify: plyer toast notification.
- send_paste: pynput keyboard controller -> Ctrl+V.
- send_enter: pynput keyboard controller -> Enter.
- register_external_reset: no-op (Windows has no SIGUSR1; reset comes from the
  tray-icon menu instead).
"""

_NOT_IMPLEMENTED = (
    "Windows support is implemented in Phase 3 — see CROSS_PLATFORM.md."
)


def play_sound(event, blocking=False):
    raise NotImplementedError(_NOT_IMPLEMENTED)


def notify(title, message):
    raise NotImplementedError(_NOT_IMPLEMENTED)


def send_paste():
    raise NotImplementedError(_NOT_IMPLEMENTED)


def send_enter():
    raise NotImplementedError(_NOT_IMPLEMENTED)


def register_external_reset(callback):
    # No external signal on Windows; the tray menu will trigger resets.
    pass
