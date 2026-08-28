"""TASK-001 — configuração."""

from app.config import CameraType, Settings


def test_defaults_are_local_first():
    s = Settings(_env_file=None)
    assert s.store_images is False
    assert s.auto_capture_enabled is False
    assert s.camera_type is CameraType.USB
    assert s.port == 8080


def test_llm_url_is_composed_from_base_and_endpoint():
    s = Settings(
        _env_file=None,
        llm_base_url="http://host.docker.internal:8001/",
        llm_endpoint="/v1/chat/completions",
    )
    assert s.llm_url == "http://host.docker.internal:8001/v1/chat/completions"


def test_auth_disabled_when_token_empty():
    assert Settings(_env_file=None, auth_token="").auth_enabled is False
    assert Settings(_env_file=None, auth_token="x").auth_enabled is True


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("CAMERA_TYPE", "file")
    monkeypatch.setenv("PORT", "9000")
    s = Settings(_env_file=None)
    assert s.camera_type is CameraType.FILE
    assert s.port == 9000
