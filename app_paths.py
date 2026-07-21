"""Frozen-aware path resolution for Whisper Dictate.

When running from source (Terminal/venv), config lives beside the code in the
repo ``.env`` — exactly as before this module existed. When running from a
PyInstaller-frozen ``.app`` bundle, the bundle's ``Contents/`` is read-only
after signing and we must not bake the owner's API key into a shipped app, so
config moves to a stable, writable, per-user location:

    ~/Library/Application Support/WhisperDictate/   (macOS)
    %APPDATA%/WhisperDictate/                        (Windows)
    ~/.config/WhisperDictate/                        (other POSIX)

On the first frozen launch we seed that file from a pre-existing dev
``~/whisper-dictate/.env`` if present (so an owner's current setup carries
over), else from the bundled ``.env.example`` template.

Stdlib-only on purpose: this module is imported at the very top of ``dictate.py``
(including in each multiprocessing spawn child), so it must stay cheap and have
no third-party dependencies.
"""
import os
import shutil
import sys

APP_NAME = "WhisperDictate"


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle (``sys.frozen`` is set)."""
    return getattr(sys, "frozen", False)


def app_support_dir() -> str:
    """Stable, writable, per-user config dir.

    Not frozen: the repo/source directory (preserves the historical behaviour
    of reading the ``.env`` that sits beside the source). Frozen: a platform-
    appropriate app-support / AppData dir.
    """
    if not is_frozen():
        return os.path.dirname(os.path.abspath(__file__))
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(base, APP_NAME)
    return os.path.join(home, ".config", APP_NAME)


def env_file_path() -> str:
    """Path to the ``.env`` config file for the current run mode."""
    return os.path.join(app_support_dir(), ".env")


def bundled_resource(name: str) -> str:
    """Path to a data file shipped inside the frozen bundle (e.g. the
    ``.env.example`` seed template). PyInstaller may place data files under
    ``Contents/Resources``, ``Contents/Frameworks``, or beside the exe depending
    on the build, so check each and return the first that exists. When not
    frozen, resolves from the source dir."""
    if not is_frozen():
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, name))
    exe_dir = os.path.dirname(sys.executable)        # Contents/MacOS
    contents = os.path.dirname(exe_dir)               # Contents
    for sub in ("Resources", "Frameworks", "MacOS"):
        candidates.append(os.path.join(contents, sub, name))
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0] if candidates else name


def _repo_env_candidate() -> str:
    """Where a pre-existing dev ``.env`` might live, for first-launch migration
    of an owner who already runs from source. Conventional clone location."""
    return os.path.join(os.path.expanduser("~"), "whisper-dictate", ".env")


def ensure_env_seeded() -> None:
    """On the first frozen launch, make sure a writable ``.env`` exists in the
    app-support dir. Seed it (in priority order) from a pre-existing dev
    ``~/whisper-dictate/.env`` (auto-migrate the owner's setup), else from the
    bundled ``.env.example``. No-op when not frozen. Best-effort: swallows
    OSError so a seeding failure never blocks startup (load_dotenv will simply
    read defaults)."""
    if not is_frozen():
        return
    env_path = env_file_path()
    if os.path.exists(env_path):
        return
    try:
        os.makedirs(app_support_dir(), exist_ok=True)
        for src in (_repo_env_candidate(), bundled_resource(".env.example")):
            if src and os.path.exists(src):
                shutil.copyfile(src, env_path)
                return
    except OSError:
        pass
