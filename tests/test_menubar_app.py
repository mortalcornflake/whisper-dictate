"""Unit tests for the pure helpers in menubar_app.py.

These avoid importing rumps (the App subclass is guarded), so they run on any
platform. The rumps-backed UI itself is exercised manually, not in CI.
"""
import os

import menubar_app as m


def test_format_elapsed():
    assert m.format_elapsed(0) == "0:00"
    assert m.format_elapsed(5) == "0:05"
    assert m.format_elapsed(65) == "1:05"
    assert m.format_elapsed(600) == "10:00"
    assert m.format_elapsed(-3) == "0:00"   # clamps negatives
    assert m.format_elapsed(9.9) == "0:09"  # truncates, not rounds


def test_truncate_collapses_whitespace():
    assert m.truncate("  hello   world  ") == "hello world"
    assert m.truncate("") == ""
    assert m.truncate(None) == ""


def test_truncate_long_text():
    out = m.truncate("x" * 100)
    assert out.endswith("…")
    assert len(out) == m._MAX_PREVIEW


def test_truncate_short_text_unchanged():
    assert m.truncate("short", limit=20) == "short"


def test_ensure_env_file_creates_from_example(tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n")
    env_path = m.ensure_env_file(str(tmp_path))
    assert env_path == os.path.join(str(tmp_path), ".env")
    assert os.path.exists(env_path)
    assert (tmp_path / ".env").read_text() == "KEY=value\n"


def test_ensure_env_file_keeps_existing(tmp_path):
    (tmp_path / ".env.example").write_text("KEY=fromexample\n")
    (tmp_path / ".env").write_text("KEY=existing\n")
    m.ensure_env_file(str(tmp_path))
    assert (tmp_path / ".env").read_text() == "KEY=existing\n"  # not overwritten


def test_ensure_env_file_no_example(tmp_path):
    # No .env.example: returns the path without creating anything.
    env_path = m.ensure_env_file(str(tmp_path))
    assert env_path == os.path.join(str(tmp_path), ".env")
    assert not os.path.exists(env_path)


def test_upsert_env_line_replaces_existing():
    content = "A=1\nSOUND_STOP=true\nB=2\n"
    assert m.upsert_env_line(content, "SOUND_STOP", "false") == "A=1\nSOUND_STOP=false\nB=2\n"


def test_upsert_env_line_appends_when_missing():
    assert m.upsert_env_line("A=1\n", "SOUND_DONE", "false") == "A=1\nSOUND_DONE=false\n"


def test_upsert_env_line_empty_content():
    assert m.upsert_env_line("", "SOUND_START", "true") == "SOUND_START=true\n"


def test_upsert_env_line_ignores_commented_line():
    # A commented example line is left intact; a real assignment is appended.
    content = "# SOUND_START=true\n"
    assert m.upsert_env_line(content, "SOUND_START", "false") == "# SOUND_START=true\nSOUND_START=false\n"


def test_upsert_env_line_no_trailing_newline_preserved():
    # Input without a trailing newline stays without one after an in-place edit.
    assert m.upsert_env_line("SOUND_STOP=true", "SOUND_STOP", "false") == "SOUND_STOP=false"


def test_persist_env_setting_roundtrip(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DICTATE_BACKEND=local\n")
    m.persist_env_setting(str(env), "SOUND_STOP", "false")
    assert env.read_text() == "DICTATE_BACKEND=local\nSOUND_STOP=false\n"
    # A second toggle replaces rather than duplicating.
    m.persist_env_setting(str(env), "SOUND_STOP", "true")
    assert env.read_text() == "DICTATE_BACKEND=local\nSOUND_STOP=true\n"
