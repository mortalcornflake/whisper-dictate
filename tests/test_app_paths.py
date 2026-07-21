"""Unit tests for app_paths.py — frozen-aware config-path resolution.

Exercises both the source (not-frozen) path and the frozen path by monkey-
patching sys.frozen / sys.platform / HOME, without actually freezing.
"""
import os
import sys

import app_paths


def test_not_frozen_by_default():
    assert app_paths.is_frozen() is False


def test_env_file_path_in_source_is_repo_env():
    # Running from source: .env sits beside the code (unchanged behaviour).
    assert app_paths.env_file_path() == os.path.join(
        os.path.dirname(os.path.abspath(app_paths.__file__)), ".env")


def test_ensure_env_seeded_noop_when_not_frozen(tmp_path, monkeypatch):
    # Not frozen -> ensure_env_seeded returns immediately and never writes.
    monkeypatch.setattr(app_paths, "env_file_path",
                        lambda: str(tmp_path / "sub" / ".env"))
    app_paths.ensure_env_seeded()
    assert not (tmp_path / "sub").exists()  # didn't even mkdir


def test_app_support_dir_frozen_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = os.path.join(
        str(tmp_path), "Library", "Application Support", app_paths.APP_NAME)
    assert app_paths.app_support_dir() == expected


def test_ensure_env_seeded_migrates_repo_env_when_frozen(tmp_path, monkeypatch):
    # Frozen + a pre-existing ~/whisper-dictate/.env -> copied into app-support,
    # so an owner's existing setup carries over to the .app on first launch.
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    repo_env = tmp_path / "whisper-dictate" / ".env"
    repo_env.parent.mkdir(parents=True)
    repo_env.write_text("DICTATE_BACKEND=local\nGROQ_API_KEY=x\n")

    app_paths.ensure_env_seeded()

    seeded = (tmp_path / "Library" / "Application Support"
              / app_paths.APP_NAME / ".env")
    assert seeded.exists()
    assert seeded.read_text() == "DICTATE_BACKEND=local\nGROQ_API_KEY=x\n"


def test_ensure_env_seeded_idempotent(tmp_path, monkeypatch):
    # Second call must not overwrite an already-seeded .env.
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    support = tmp_path / "Library" / "Application Support" / app_paths.APP_NAME
    support.mkdir(parents=True)
    (support / ".env").write_text("KEEP=me\n")

    app_paths.ensure_env_seeded()

    assert (support / ".env").read_text() == "KEEP=me\n"


def test_bundled_resource_finds_file_in_resources(tmp_path, monkeypatch):
    # Simulate a .app layout: Contents/MacOS/<exe>, Contents/Resources/<name>.
    # PyInstaller places data files under Resources, not beside the exe.
    contents = tmp_path / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    exe = macos / "WhisperDictate"
    exe.write_text("")
    (resources / ".env.example").write_text("KEY=v\n")

    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert app_paths.bundled_resource(".env.example") == str(resources / ".env.example")
