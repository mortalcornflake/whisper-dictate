"""Unit tests for pure helpers in dictate.py.

Importing dictate pulls in numpy/sounddevice/pynput/pyperclip (installed via
requirements.txt); it does NOT start the app (guarded by __main__).
"""
import numpy as np
from pynput import keyboard

import dictate


def test_trim_trailing_silence_empty():
    out = dictate.trim_trailing_silence(np.array([], dtype=np.int16))
    assert len(out) == 0


def test_trim_trailing_silence_all_silence():
    audio = np.zeros(16000, dtype=np.int16)
    assert len(dictate.trim_trailing_silence(audio)) == 0


def test_trim_trailing_silence_keeps_speech_trims_tail():
    sr = 16000
    speech = np.ones(sr, dtype=np.int16) * 1000   # 1s above threshold
    silence = np.zeros(sr * 2, dtype=np.int16)    # 2s trailing silence
    audio = np.concatenate([speech, silence])
    out = dictate.trim_trailing_silence(audio, sample_rate=sr, buffer_secs=0.3)
    assert sr <= len(out) <= sr + int(0.3 * sr) + 1   # speech + ~0.3s buffer
    assert len(out) < len(audio)                       # tail was trimmed


def test_is_hallucination():
    assert dictate._is_hallucination("Thank you.")
    assert dictate._is_hallucination("  okay  ")
    assert dictate._is_hallucination("YOU")
    assert not dictate._is_hallucination("hello world")
    assert not dictate._is_hallucination("thank you for the help")
    # Expanded phantom set (silence/noise phantoms seen in the wild):
    assert dictate._is_hallucination("hmm")
    assert dictate._is_hallucination("Good job.")
    assert dictate._is_hallucination("Thanks for watching.")
    assert dictate._is_hallucination("Please subscribe.")
    assert dictate._is_hallucination("Be certain.")
    assert dictate._is_hallucination("you")
    assert not dictate._is_hallucination("you too")            # extra word -> real
    assert not dictate._is_hallucination("okay let's go")      # extra words -> real
    # Empty / whitespace-only / pure-special-token -> treated as hallucination.
    assert dictate._is_hallucination("")
    assert dictate._is_hallucination("   ")
    assert dictate._is_hallucination("[BLANK_AUDIO]")
    assert dictate._is_hallucination("[MUSIC]")


def test_get_clipboard_coerces_none(monkeypatch):
    monkeypatch.setattr(dictate.pyperclip, "paste", lambda: None)
    assert dictate.get_clipboard() == ""   # regression: image/file clipboard


def test_get_clipboard_passthrough(monkeypatch):
    monkeypatch.setattr(dictate.pyperclip, "paste", lambda: "hello")
    assert dictate.get_clipboard() == "hello"


def test_parse_hotkey():
    assert dictate.parse_hotkey("ctrl_r") == keyboard.Key.ctrl_r
    assert dictate.parse_hotkey("CTRL_R") == keyboard.Key.ctrl_r   # case-insensitive
    assert dictate.parse_hotkey("nonsense") == keyboard.Key.alt_r  # safe default


def test_env_int_fallback(monkeypatch):
    monkeypatch.setenv("SOME_INT", "not-a-number")
    assert dictate._env_int("SOME_INT", 300) == 300
    monkeypatch.setenv("SOME_INT", "45")
    assert dictate._env_int("SOME_INT", 300) == 45
    monkeypatch.delenv("SOME_INT", raising=False)
    assert dictate._env_int("SOME_INT", 300) == 300


def test_env_bool():
    import os
    for val, expected in (("true", True), ("1", True), ("YES", True),
                          ("false", False), ("0", False), ("", None), ("nonsense", False)):
        if val == "":
            os.environ.pop("SOME_BOOL", None)
            assert dictate._env_bool("SOME_BOOL", "DEFAULT") == "DEFAULT"  # missing -> default
        else:
            os.environ["SOME_BOOL"] = val
            assert dictate._env_bool("SOME_BOOL", False) is expected
    os.environ.pop("SOME_BOOL", None)


def test_resolve_modifier_keys_shift():
    keys = dictate.resolve_modifier_keys("shift")
    # Left shift must be recognised regardless of which variant the OS reports.
    assert keyboard.Key.shift in keys or keyboard.Key.shift_l in keys


def test_resolve_modifier_keys_unknown_defaults_shift():
    assert dictate.resolve_modifier_keys("bogus") == dictate.resolve_modifier_keys("shift")


def test_resolve_modifier_keys_excludes_hotkey():
    # A ctrl-family hotkey must not appear in a ctrl modifier set (would self-trigger).
    keys = dictate.resolve_modifier_keys("ctrl", exclude=keyboard.Key.ctrl_r)
    assert keyboard.Key.ctrl_r not in keys


def test_collapse_whitespace():
    # Segment line breaks from whisper become single spaces -> one block.
    assert dictate.collapse_whitespace("one\ntwo\nthree") == "one two three"
    assert dictate.collapse_whitespace("  a \n\n  b  ") == "a b"
    assert dictate.collapse_whitespace("") == ""
    assert dictate.collapse_whitespace("\n \n") == ""
    assert dictate.collapse_whitespace("already one block") == "already one block"


def test_archive_recording(tmp_path, monkeypatch):
    monkeypatch.setattr(dictate, "RECORDINGS_DIR", str(tmp_path))
    # Fixed timestamp so the basename is deterministic.
    when = 1751385600.123  # 2025-07-01 in local time; ms suffix from .123
    base = dictate.archive_recording(b"RIFFfakewav", "hello world", when=when)
    assert base is not None
    assert (tmp_path / (base + ".wav")).read_bytes() == b"RIFFfakewav"
    assert (tmp_path / (base + ".txt")).read_text(encoding="utf-8") == "hello world"
    # index.jsonl gets one JSON row with the transcript + byte count.
    import json as _json
    rows = (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = _json.loads(rows[0])
    assert row["text"] == "hello world"
    assert row["audio"] == base + ".wav"
    assert row["audio_bytes"] == len(b"RIFFfakewav")


def test_archive_recording_empty_audio_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(dictate, "RECORDINGS_DIR", str(tmp_path))
    assert dictate.archive_recording(b"", "text") is None
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_should_latch():
    mods = {keyboard.Key.shift, keyboard.Key.shift_l}
    # Enabled + a modifier held -> latch.
    assert dictate.should_latch(True, mods, {keyboard.Key.shift_l, keyboard.Key.alt_r})
    # Enabled but no modifier held -> no latch (normal press-and-hold).
    assert not dictate.should_latch(True, mods, {keyboard.Key.alt_r})
    # Disabled -> never latch even with modifier held.
    assert not dictate.should_latch(False, mods, {keyboard.Key.shift_l})


def test_clean_transcript_strips_special_tokens():
    assert dictate._clean_transcript("[BLANK_AUDIO]") == ""
    assert dictate._clean_transcript("(applause)") == ""
    assert dictate._clean_transcript("yeah [MUSIC]") == "yeah"
    assert dictate._clean_transcript("hello [BLANK_AUDIO] world") == "hello world"
    # Conservative: arbitrary bracketed text survives.
    assert dictate._clean_transcript("see [Figure 1] here") == "see [Figure 1] here"
    assert dictate._clean_transcript("") == ""
    assert dictate._clean_transcript("   ") == ""


def test_collapse_consecutive_repeats():
    assert dictate._collapse_consecutive_repeats("yeah yeah yeah yeah") == "yeah"
    assert dictate._collapse_consecutive_repeats("the, the, the, the") == "the"
    assert dictate._collapse_consecutive_repeats("The the the the the") == "The"  # case-insensitive
    # Below the 4+ threshold -> unchanged.
    assert dictate._collapse_consecutive_repeats("yeah yeah yeah") == "yeah yeah yeah"
    assert dictate._collapse_consecutive_repeats("I really really like it") == "I really really like it"
    # Normal speech untouched.
    assert dictate._collapse_consecutive_repeats("I went to the store") == "I went to the store"
    assert dictate._collapse_consecutive_repeats("") == ""


def test_is_repetitive_loop():
    assert dictate._is_repetitive_loop("thank you thank you thank you thank you")
    assert dictate._is_repetitive_loop("the the the the the the the the")
    # Real speech: many unique words -> not a loop.
    assert not dictate._is_repetitive_loop("I went to the store to buy some milk")
    # Too short to judge -> not flagged (handled by _collapse_consecutive_repeats instead).
    assert not dictate._is_repetitive_loop("the the the the")
    assert not dictate._is_repetitive_loop("")
    assert not dictate._is_repetitive_loop("yeah yeah")


def test_has_speech_rejects_silence():
    sr = 16000
    assert not dictate.has_speech(np.zeros(sr, dtype=np.int16), sample_rate=sr)
    assert not dictate.has_speech(np.array([], dtype=np.int16), sample_rate=sr)
    assert not dictate.has_speech(None, sample_rate=sr)


def test_has_speech_accepts_real_speech():
    sr = 16000
    rng = np.random.default_rng(0)
    bg = lambda n, amp: rng.integers(-amp, amp + 1, size=n).astype(np.int16)
    # ~0.25s quiet lead, 0.4s loud "speech" burst, quiet tail.
    audio = np.concatenate([
        bg(sr // 4, 20),
        bg(int(0.4 * sr), 5000),
        bg(sr // 4, 20),
    ])
    assert dictate.has_speech(audio, sample_rate=sr)


def test_has_speech_rejects_transient():
    sr = 16000
    # A single brief spike (desk-tap / mic-bump) in otherwise silence: loud but
    # not sustained -> rejected by both the duration and contiguous-run checks.
    audio = np.zeros(int(0.5 * sr), dtype=np.int16)
    audio[5000:5060] = 3000  # 60 samples (~1 frame) of energy
    assert not dictate.has_speech(audio, sample_rate=sr)


def test_has_speech_accepts_continuous_speech():
    # Regression: a continuously-spoken dictation has no quiet gaps, so its
    # median frame RMS is speech-level. A median-relative threshold rejected
    # this as "no speech" (the 9-10s false-reject bug). An absolute floor
    # accepts it.
    sr = 16000
    rng = np.random.default_rng(1)
    audio = rng.integers(-3000, 3001, size=int(1.5 * sr)).astype(np.int16)
    assert dictate.has_speech(audio, sample_rate=sr)
