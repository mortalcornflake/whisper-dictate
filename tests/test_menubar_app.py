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
