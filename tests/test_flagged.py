"""Tests for the flagged-transcription log (flagged.py)."""
import flagged


def test_read_recent_missing_log(tmp_path, monkeypatch):
    monkeypatch.setattr(flagged.app_paths, "app_support_dir", lambda: str(tmp_path))
    assert flagged.read_recent() == []   # no file -> []


def test_append_and_read_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(flagged.app_paths, "app_support_dir", lambda: str(tmp_path))
    flagged.append_flagged("phrase loop x4 ('I want to fly in,')",
                           "I want to fly in, " * 4, recording="2026-07-16_12-42-21_568.wav")
    flagged.append_flagged("leaked special token", "hello [BLANK_AUDIO] world")

    entries = flagged.read_recent()
    assert len(entries) == 2
    # Oldest first; ts then reason.
    assert entries[0][1].startswith("phrase loop")
    assert entries[1][1] == "leaked special token"

    # The log is markdown the owner can read + annotate.
    content = open(flagged.flagged_log_path(), encoding="utf-8").read()
    assert "**Note:**" in content                 # the annotation line
    assert "**Recording:** 2026-07-16_12-42-21_568.wav" in content
    assert "hello [BLANK_AUDIO] world" in content
