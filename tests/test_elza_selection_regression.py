import io
import json

from LS_Elza import selection_intent
from ls_web import elza_adapter
from ls_web import elza_controller
from ls_web import elza_selection_bridge


def test_local_wav_minus_upload_parser_builds_exact_constraints(monkeypatch):
    monkeypatch.setattr(elza_adapter, "normalize_tag_filter", lambda values: values, raising=False)
    result = elza_adapter.parse_ls_elza_selection_intent(
        "Parādi visus lokālos Wav - Uplod"
    )

    assert result["filters"]["local_audio_filter"] == "with"
    assert result["local_audio_extensions"] == ["wav"]
    assert result["exclude_ui_types"] == ["Upload"]
    assert "Local WAV" in result["summary"]
    assert "Bez Type: Upload" in result["summary"]


def test_selection_tool_contract_supports_local_wav_minus_upload():
    tool = selection_intent.get_selection_tool_definition()
    properties = tool["parameters"]["properties"]

    assert "local_audio_extensions" in properties
    assert "exclude_ui_types" in properties

    normalized = selection_intent.normalize_selection_request({
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "",
        "local_audio": "with",
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": None,
        "title_query": "",
        "exact_stem_count": 0,
        "local_audio_extensions": ["WAV"],
        "exclude_ui_types": ["Upload"],
    })

    assert normalized["local_audio_extensions"] == ["wav"]
    assert normalized["exclude_ui_types"] == ["Upload"]


def test_host_bridge_preserves_exact_wav_and_excluded_type():
    request = {
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "",
        "local_audio": "with",
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": None,
        "title_query": "",
        "exact_stem_count": 0,
        "local_audio_extensions": ["wav"],
        "exclude_ui_types": ["Upload"],
    }

    result = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda _value: "",
        resolve_local_family=lambda _value: "",
        normalize_tags=lambda values: values,
    )

    assert result["filters"]["local_audio_filter"] == "with"
    assert result["local_audio_extensions"] == ["wav"]
    assert result["exclude_ui_types"] == ["Upload"]
    assert "Local WAV" in result["summary"]
    assert "Bez Type: Upload" in result["summary"]


def test_local_wav_minus_upload_returns_precise_track_id_view(monkeypatch):
    monkeypatch.setattr(elza_adapter, "normalize_tag_filter", lambda values: values, raising=False)
    monkeypatch.setattr(
        elza_adapter,
        "search_tracks",
        lambda **_kwargs: [
            {
                "id": "wav-keep",
                "title": "Keep WAV",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\Keep WAV.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\Keep WAV.wav",
                "ui_type": "Song",
                "kind": "Song",
            },
            {
                "id": "wav-upload",
                "title": "Upload WAV",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\Upload WAV.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\Upload WAV.wav",
                "ui_type": "Upload",
                "kind": "Upload",
            },
            {
                "id": "mp3-keep",
                "title": "Keep MP3",
                "workspace": "W",
                "local_wav": "",
                "local_mp3": r"E:\\Audio\\Keep MP3.mp3",
                "ui_best_local_audio_path": r"E:\\Audio\\Keep MP3.mp3",
                "ui_type": "Song",
                "kind": "Song",
            },
        ],
        raising=False,
    )
    monkeypatch.setattr(
        elza_adapter,
        "ls_elza_append_chat_exchange",
        lambda *_args, **_kwargs: {},
        raising=False,
    )

    response = elza_adapter.get_ls_elza_local_readonly_response({
        "action": "send",
        "message": "Parādi visus lokālos Wav - Uplod",
    })

    assert response["ok"] is True
    assert response["ls_view_label"] == "Atvērt atlasi LS"
    assert "track_ids=wav-keep" in response["ls_view_url"]
    assert "rows=all" in response["ls_view_url"]
    assert "wav-upload" not in response["ls_view_url"]
    assert "mp3-keep" not in response["ls_view_url"]
    assert "ls_save_view_url" not in response
    assert "Local WAV" in response["answer"]
    assert "Bez Type: Upload" in response["answer"]


def test_plain_ask_short_circuits_to_deterministic_selection(monkeypatch):
    payload = {
        "action": "send",
        "message": "Parādi visus lokālos Wav bez Uplod",
        "selected_mode": "",
    }
    raw = json.dumps(payload).encode("utf-8")
    local_result = {
        "ok": True,
        "answer": "Atrasti 1 ieraksti.",
        "ls_view_url": "/?track_ids=wav-keep&rows=all",
        "ls_view_label": "Atvērt atlasi LS",
    }
    calls = []

    monkeypatch.setattr(
        elza_controller,
        "get_ls_elza_local_readonly_response",
        lambda received: calls.append(received) or local_result,
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "handle_ls_elza_action",
        lambda _payload: (_ for _ in ()).throw(
            AssertionError("AI service must not run for deterministic selection")
        ),
        raising=False,
    )

    class Handler(elza_controller.ElzaControllerMixin):
        headers = {
            "Content-Length": str(len(raw)),
            "Origin": "",
        }
        rfile = io.BytesIO(raw)

        def __init__(self):
            self.sent = []

        def send_json_response(self, data, status=200):
            self.sent.append((status, data))

    handler = Handler()
    handler.ls_assistant_chat()

    assert len(calls) == 1
    assert calls[0]["action"] == "send"
    assert calls[0]["message"] == "Parādi visus lokālos Wav bez Uplod"
    assert handler.sent == [(200, local_result)]
