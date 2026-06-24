"""Platform-specific OS integration (sound, paste, notifications, reset).

Selects the right backend for the current OS so the rest of the app stays
platform-neutral. Add a new platform by creating a module here and wiring it
into ``_load_backend``.

Note: this package is deliberately NOT named ``platform`` to avoid shadowing the
Python standard-library module of that name.

Clipboard get/set is intentionally NOT part of this interface — ``pyperclip`` is
already cross-platform, so the core handles the clipboard directly.
"""
import sys


def _load_backend():
    if sys.platform == "darwin":
        from . import darwin as backend
    elif sys.platform == "win32":
        from . import windows as backend
    else:
        raise NotImplementedError(
            f"Unsupported platform: {sys.platform!r}. "
            "Only macOS (darwin) and Windows (win32) are supported."
        )
    return backend


_backend = _load_backend()

# Re-export the platform interface.
play_sound = _backend.play_sound
notify = _backend.notify
send_paste = _backend.send_paste
send_enter = _backend.send_enter
register_external_reset = _backend.register_external_reset
