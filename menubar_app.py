"""macOS menu bar app for Whisper Dictate.

The macOS counterpart to ``tray_app.py`` (Windows). A ``rumps`` menu bar app owns
the main thread (required for any Cocoa UI) while the keyboard listener runs in a
background thread, mirroring how the Windows tray owns the main thread. The menu
bar shows recording state and offers Pause/Resume, Reset, copy-last-transcription,
and quick access to the settings (.env) and log files.

This is deliberately NOT a 1:1 clone of the Windows tray — it leans into what
makes sense on macOS (an emoji status glyph in the bar, ``open -t`` for settings,
a live recording timer, last-transcription preview).

macOS-only: ``rumps`` wraps Cocoa, so the import is guarded and the App subclass
is only defined when ``rumps`` is importable. ``dictate.py`` imports
``run_with_menubar`` lazily on the darwin path (mirroring ``run_with_tray`` on
win32). The pure helpers below avoid importing ``rumps`` so they stay unit-testable
on any platform.
"""
import os
import subprocess
import time

IDLE_GLYPH = "🎙"
REC_GLYPH = "🔴"
PAUSED_GLYPH = "⏸"
_MAX_PREVIEW = 48


def format_elapsed(seconds):
    """Format a duration in seconds as ``M:SS`` (negatives clamp to zero)."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def truncate(text, limit=_MAX_PREVIEW):
    """Collapse whitespace and shorten text to a single-line menu preview."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def ensure_env_file(repo_dir):
    """Return the repo ``.env`` path, creating it from ``.env.example`` the first
    time so "Open settings" always has something to show. Best-effort."""
    env_path = os.path.join(repo_dir, ".env")
    if not os.path.exists(env_path):
        example = os.path.join(repo_dir, ".env.example")
        if os.path.exists(example):
            try:
                import shutil
                shutil.copyfile(example, env_path)
            except OSError:
                pass
    return env_path


def _open_in_editor(path):
    """Open a file in the user's default text editor via macOS ``open -t``."""
    try:
        subprocess.Popen(
            ["open", "-t", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


# Friendly labels for the per-event sound toggles, in menu order.
_SOUND_LABELS = (
    ("start", "Start (key press)"),
    ("stop", "Stop (key release)"),
    ("done", "Done (transcription pasted)"),
    ("warning", "Warning (near auto-stop)"),
)


def upsert_env_line(content, key, value):
    """Return ``.env`` ``content`` with ``KEY=value`` set: replace the first
    uncommented ``KEY=`` line if present, otherwise append one. Commented example
    lines are left intact. Pure string transform so it stays unit-testable."""
    lines = content.splitlines()
    new_line = f"{key}={value}"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    text = "\n".join(lines)
    if content == "" or content.endswith("\n"):
        text += "\n"
    return text


def persist_env_setting(env_path, key, value):
    """Best-effort write of ``KEY=value`` into the ``.env`` file so a menu-bar
    sound toggle survives a restart. Silently no-ops on any I/O error."""
    try:
        with open(env_path, "r") as f:
            content = f.read()
    except OSError:
        content = ""
    try:
        with open(env_path, "w") as f:
            f.write(upsert_env_line(content, key, value))
    except OSError:
        pass


try:
    import rumps
except ImportError:  # not macOS / not installed — keep the module importable
    rumps = None


if rumps is not None:

    class _WhisperDictateMenuBar(rumps.App):
        """rumps app that polls the listener and reflects its state in the bar."""

        def __init__(self, listener, hotkey_name, repo_dir, log_path, on_quit,
                     sound_config=None):
            super().__init__("Whisper Dictate", title=IDLE_GLYPH, quit_button=None)
            self._listener = listener
            self._hotkey_name = hotkey_name or "the hotkey"
            self._repo_dir = repo_dir
            self._log_path = log_path
            self._on_quit_cb = on_quit
            # Same dict object as dictate.SOUNDS_ENABLED — mutating it here changes
            # what the core plays, with no UI->core coupling beyond this handle.
            self._sound_config = sound_config if sound_config is not None else {}
            self._env_path = os.path.join(repo_dir, ".env")
            self._rec_started = None
            self._was_recording = False
            self._paused = False

            self._status = rumps.MenuItem(self._idle_status_text())
            self._status.set_callback(None)  # informational, non-clickable
            self._preview = rumps.MenuItem("Last: —")
            self._preview.set_callback(None)
            self._copy_item = rumps.MenuItem(
                "Copy last transcription", callback=self._on_copy)
            self._copy_item.set_callback(None)  # enabled once there's text
            self._pause_item = rumps.MenuItem(
                "Pause listening", callback=self._on_pause)

            # Per-event sound toggles — a checkmark submenu that flips
            # self._sound_config (shared with the core) and persists to .env.
            self._sounds_menu = rumps.MenuItem("Sounds")
            self._sound_items = {}
            for event, label in _SOUND_LABELS:
                if event not in self._sound_config:
                    continue
                item = rumps.MenuItem(label, callback=self._make_sound_toggle(event))
                item.state = 1 if self._sound_config[event] else 0
                self._sounds_menu.add(item)
                self._sound_items[event] = item

            self.menu = [
                self._status,
                None,
                self._preview,
                self._copy_item,
                None,
                self._pause_item,
                rumps.MenuItem("Reset recorder", callback=self._on_reset),
                self._sounds_menu,
                None,
                rumps.MenuItem("Open settings (.env)…", callback=self._on_settings),
                rumps.MenuItem("Open log…", callback=self._on_log),
                None,
                rumps.MenuItem("Quit Whisper Dictate", callback=self._on_quit),
            ]

            # Poll the listener so the bar tracks recording state without the core
            # ever needing to call into the UI (keeps the dependency one-way).
            self._timer = rumps.Timer(self._tick, 0.5)
            self._timer.start()

        def _idle_status_text(self):
            return f"Ready · hold {self._hotkey_name} to dictate"

        def _tick(self, _timer):
            recording = bool(getattr(self._listener, "is_recording", False))
            if recording and not self._was_recording:
                self._rec_started = time.time()
            elif not recording:
                self._rec_started = None
            self._was_recording = recording

            if recording:
                self.title = REC_GLYPH
                elapsed = format_elapsed(time.time() - (self._rec_started or time.time()))
                self._status.title = f"Recording… {elapsed}"
            elif self._paused:
                self.title = PAUSED_GLYPH
                self._status.title = "Paused — click Resume to listen"
            else:
                self.title = IDLE_GLYPH
                self._status.title = self._idle_status_text()

            last = getattr(self._listener, "last_transcription", "") or ""
            self._preview.title = f"Last: {truncate(last)}" if last else "Last: —"
            self._copy_item.set_callback(self._on_copy if last else None)

        # ---- menu actions ----
        def _on_copy(self, _item):
            last = getattr(self._listener, "last_transcription", "") or ""
            if last:
                try:
                    import pyperclip
                    pyperclip.copy(last)
                except Exception:
                    pass

        def _on_pause(self, item):
            if self._paused:
                self._listener.start_listening()
                self._paused = False
                item.title = "Pause listening"
            else:
                self._listener.stop_listening()
                self._paused = True
                item.title = "Resume listening"

        def _on_reset(self, _item):
            self._listener.reset(reason="Menu bar reset")

        def _make_sound_toggle(self, event):
            """Build the callback for one sound's menu item. Flips the shared
            config (so the core plays/mutes it immediately), updates the checkmark,
            and persists the choice to .env so it sticks across restarts."""
            def _toggle(item):
                enabled = not self._sound_config.get(event, False)
                self._sound_config[event] = enabled
                item.state = 1 if enabled else 0
                persist_env_setting(
                    self._env_path, f"SOUND_{event.upper()}",
                    "true" if enabled else "false")
            return _toggle

        def _on_settings(self, _item):
            _open_in_editor(ensure_env_file(self._repo_dir))

        def _on_log(self, _item):
            for candidate in (self._log_path,
                              os.path.join(self._repo_dir, "dictate.log")):
                if candidate and os.path.exists(candidate):
                    _open_in_editor(candidate)
                    return

        def _on_quit(self, _item):
            # rumps.quit_application() calls Cocoa terminate, which exits the
            # process directly — so cleanup must happen HERE, before quitting, not
            # after run() (which never returns) or via atexit (which Cocoa skips).
            if self._on_quit_cb is not None:
                try:
                    self._on_quit_cb()
                except Exception:
                    pass
            else:
                try:
                    self._listener.stop_listening()
                except Exception:
                    pass
            rumps.quit_application()


def run_with_menubar(listener, hotkey_name=None, log_path=None, on_quit=None,
                     sound_config=None):
    """Run the keyboard listener (background thread) plus the menu bar app (this
    thread). Blocks until the user chooses Quit. ``on_quit`` is invoked from the
    Quit handler for teardown (stop listener, kill subprocesses) because Cocoa's
    terminate exits the process without returning here. ``sound_config`` is the
    core's live per-event sound dict (dictate.SOUNDS_ENABLED), shown as a toggle
    submenu. Raises RuntimeError if rumps isn't available."""
    if rumps is None:
        raise RuntimeError("rumps is not installed — macOS menu bar unavailable")
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    listener.start_listening()
    app = _WhisperDictateMenuBar(listener, hotkey_name, repo_dir, log_path, on_quit,
                                 sound_config=sound_config)
    app.run()
