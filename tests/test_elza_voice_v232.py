import inspect
from types import SimpleNamespace

import pytest

from LS_Elza import LS_ELZA_PACKAGE_VERSION
from LS_Elza import service as elza_service
from LS_Elza import ui as elza_ui
from ls_web import elza_controller


def test_elza_v232_visible_identity_and_rendered_composer():
    assert LS_ELZA_PACKAGE_VERSION == "2.32"
    assert "Elza v2.32" in elza_ui.render_ls_elza_dialog_markup()

    rendered = elza_ui.render_ls_elza_assets(
        "library",
        view_context={},
        docked=False,
        local_family_title="",
        app_version="v2.28",
        opacity=50,
    )

    assert 'data-elza-v232="composer"' in rendered
    assert "UX pārbaude" in rendered
    assert "Testēt funkciju" in rendered
    assert "Track analīze" in rendered
    assert "Koda analīze" in rendered
    assert "Balss" in rendered
    assert "createAnalyser" in rendered
    assert "getByteFrequencyData" in rendered
    assert "@keyframes" not in rendered


def test_elza_stt_transcribes_latvian_webm(monkeypatch):
    captured = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="Parādi visus lokālos WAV bez Upload")

    fake_client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=FakeTranscriptions())
    )
    monkeypatch.setattr(elza_service, "get_openai_client", lambda: fake_client)

    result = elza_service.transcribe_ls_elza_audio(
        b"not-empty-audio",
        "audio/webm;codecs=opus",
    )

    assert result == "Parādi visus lokālos WAV bez Upload"
    assert captured["model"] == "gpt-4o-mini-transcribe"
    assert captured["language"] == "lv"
    assert captured["file"][0].endswith(".webm")
    assert captured["file"][1] == b"not-empty-audio"
    assert captured["file"][2] == "audio/webm"


def test_elza_stt_rejects_unsupported_audio_type():
    with pytest.raises(elza_service.LSElzaError) as error:
        elza_service.transcribe_ls_elza_audio(
            b"not-empty-audio",
            "audio/flac",
        )

    assert error.value.status == 415
    assert error.value.code == "unsupported_stt_audio"


def test_elza_controller_keeps_local_stt_route():
    source = inspect.getsource(elza_controller)
    assert 'if path == "/ls-elza-stt":' in source
    assert "def ls_elza_stt" in source
    assert "transcribe_ls_elza_audio" in source
