"""Unit tests for the faster-whisper hardware-detection logic.

These import nothing heavy — faster_whisper_backend only uses stdlib at module
level (faster_whisper/ctranslate2/pynvml are imported lazily), so these run
anywhere without a GPU or the faster-whisper package installed.
"""
import faster_whisper_backend as fw


def _clear_env(monkeypatch):
    for k in ("DICTATE_DEVICE", "DICTATE_COMPUTE_TYPE", "WHISPER_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_choose_model_cuda_by_vram(monkeypatch):
    _clear_env(monkeypatch)
    assert fw._choose_model("cuda", 8) == "large-v3-turbo"
    assert fw._choose_model("cuda", 6) == "large-v3-turbo"
    assert fw._choose_model("cuda", 5) == "medium"
    assert fw._choose_model("cuda", 4) == "medium"
    assert fw._choose_model("cuda", 3) == "small.en"
    assert fw._choose_model("cuda", None) == "large-v3-turbo"  # GPU present, VRAM unknown


def test_choose_model_cpu(monkeypatch):
    _clear_env(monkeypatch)
    assert fw._choose_model("cpu", None) == "base.en"


def test_choose_model_env_override(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "tiny.en")
    assert fw._choose_model("cuda", 8) == "tiny.en"
    assert fw._choose_model("cpu", None) == "tiny.en"


def test_choose_compute_type(monkeypatch):
    _clear_env(monkeypatch)
    assert fw._choose_compute_type("cuda") == "float16"
    assert fw._choose_compute_type("cpu") == "int8"


def test_choose_compute_type_override(monkeypatch):
    monkeypatch.setenv("DICTATE_COMPUTE_TYPE", "int8_float16")
    assert fw._choose_compute_type("cuda") == "int8_float16"
    assert fw._choose_compute_type("cpu") == "int8_float16"


def test_detect_device_override(monkeypatch):
    monkeypatch.setenv("DICTATE_DEVICE", "cpu")
    assert fw._detect_device() == "cpu"
    monkeypatch.setenv("DICTATE_DEVICE", "CUDA")  # normalised to lowercase
    assert fw._detect_device() == "cuda"


def test_is_available_returns_bool():
    assert isinstance(fw.is_available(), bool)
