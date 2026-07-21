"""Append-only log of detected Whisper hallucinations, for later review.

When the core detects a likely hallucination/loop in a raw transcript
(``_detect_output_failure`` in dictate.py), it appends an entry here. The owner
reviews the log from the menu bar ("Flagged transcriptions") and can add a
**Note:** to any entry for a later session.

Markdown on purpose: human-editable (annotate in any text editor) and trivial
for a future Claude session to read back. Path follows the frozen-aware
resolver (repo dir when running from source; app-support dir when frozen).
"""
import os
import time

import app_paths

_HEADER_PREFIX = "## "   # each entry starts with "## <ts> — <reason>"


def flagged_log_path():
    """Path to ``flagged.md`` (repo dir from source; app-support dir frozen)."""
    return os.path.join(app_paths.app_support_dir(), "flagged.md")


def append_flagged(reason, text, recording=None):
    """Append a flagged event. Best-effort — never raises (a logging failure
    must not break dictation)."""
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        rec = recording or "(not archived)"
        body = (text or "").strip().replace("\n", " ")
        entry = (
            f"\n{_HEADER_PREFIX}{ts} — {reason}\n"
            f"**Recording:** {rec}\n"
            f"**Text:** {body}\n"
            f"**Note:** \n\n---\n"
        )
        os.makedirs(app_paths.app_support_dir(), exist_ok=True)
        with open(flagged_log_path(), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass


def read_recent(limit=10):
    """Return ``[(ts, reason), ...]`` for the most recent entries (newest last).
    Best-effort; returns ``[]`` if the log is missing or unreadable."""
    try:
        with open(flagged_log_path(), "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        if line.startswith(_HEADER_PREFIX) and " — " in line:
            ts, reason = line[len(_HEADER_PREFIX):].rstrip().split(" — ", 1)
            entries.append((ts, reason))
    return entries[-limit:]
