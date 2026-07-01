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


def test_should_latch():
    mods = {keyboard.Key.shift, keyboard.Key.shift_l}
    # Enabled + a modifier held -> latch.
    assert dictate.should_latch(True, mods, {keyboard.Key.shift_l, keyboard.Key.alt_r})
    # Enabled but no modifier held -> no latch (normal press-and-hold).
    assert not dictate.should_latch(True, mods, {keyboard.Key.alt_r})
    # Disabled -> never latch even with modifier held.
    assert not dictate.should_latch(False, mods, {keyboard.Key.shift_l})
