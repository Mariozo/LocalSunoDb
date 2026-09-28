from pathlib import Path

from LS_Elza import LS_ELZA_PACKAGE_VERSION, selection_intent, ui
from LS_Elza import selection_guard
from ls_web import elza_adapter
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


def test_elza_visible_identity_and_ask_router_contract():
    assert LS_ELZA_PACKAGE_VERSION == "2.32"
    assert "Elza v2.32" in ui.render_ls_elza_dialog_markup()
    service_script = ui.render_ls_elza_script_service_assets()
    assert r"\bwav\b" in service_script
    assert "uplod" in service_script


def test_selection_tool_contract_supports_anywhere_query():
    tool = selection_intent.get_selection_tool_definition()
    properties = tool["parameters"]["properties"]
    assert "anywhere_query" in properties

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
        "local_audio_extensions": ["wav"],
        "exclude_ui_types": [],
        "anywhere_query": "Elizabete",
    })

    assert normalized["anywhere_query"] == "Elizabete"


def test_host_bridge_preserves_anywhere_query_with_wav():
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
        "exclude_ui_types": [],
        "anywhere_query": "Elizabete",
    }

    result = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda _value: "",
        resolve_local_family=lambda _value: "",
        normalize_tags=lambda values: values,
    )

    assert result["filters"]["local_audio_filter"] == "with"
    assert result["local_audio_extensions"] == ["wav"]
    assert result["anywhere_query"] == "Elizabete"
    assert "Anywhere: Elizabete" in result["summary"]


def test_wav_anywhere_query_matches_name_id_lyrics_prompt_or_tags(monkeypatch):
    monkeypatch.setattr(
        elza_adapter,
        "search_tracks",
        lambda **_kwargs: [
            {
                "id": "wav-title",
                "title": "Elizabete Title",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\title.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\title.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "",
                "user_tags": "",
            },
            {
                "id": "elizabete-id",
                "title": "ID match",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\id.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\id.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "",
                "user_tags": "",
            },
            {
                "id": "wav-lyrics",
                "title": "Lyrics match",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\lyrics.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\lyrics.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "Elizabete ir šajā tekstā",
                "prompt": "",
                "user_tags": "",
            },
            {
                "id": "wav-prompt",
                "title": "Prompt match",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\prompt.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\prompt.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "vokāls Elizabete",
                "user_tags": "",
            },
            {
                "id": "wav-tag",
                "title": "Tag match",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\tag.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\tag.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "",
                "user_tags": "#Elizabete #demo",
            },
            {
                "id": "wav-no-match",
                "title": "Other",
                "workspace": "W",
                "local_wav": r"E:\\Audio\\other.wav",
                "local_mp3": "",
                "ui_best_local_audio_path": r"E:\\Audio\\other.wav",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "",
                "user_tags": "#demo",
            },
            {
                "id": "mp3-tag",
                "title": "MP3 tag match",
                "workspace": "W",
                "local_wav": "",
                "local_mp3": r"E:\\Audio\\tag.mp3",
                "ui_best_local_audio_path": r"E:\\Audio\\tag.mp3",
                "ui_type": "Song",
                "kind": "Song",
                "lyrics": "",
                "prompt": "",
                "user_tags": "#Elizabete",
            },
        ],
        raising=False,
    )

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {"local_audio_filter": "with"},
        "local_audio_extensions": ["wav"],
        "exclude_ui_types": [],
        "anywhere_query": "Elizabete",
        "summary": "Local WAV + Anywhere: Elizabete",
        "save_name": "Local WAV + Anywhere: Elizabete",
    }, limit=20)

    assert result["matched_count"] == 5
    assert "track_ids=" in result["view_url"]
    for track_id in (
        "wav-title",
        "elizabete-id",
        "wav-lyrics",
        "wav-prompt",
        "wav-tag",
    ):
        assert track_id in result["view_url"]
    assert "wav-no-match" not in result["view_url"]
    assert "mp3-tag" not in result["view_url"]
    assert result["save_view_supported"] is False



def test_elza_v238_voice_composer_contract():
    assert LS_ELZA_PACKAGE_VERSION == "2.38"
    assert "Elza v2.32" in ui.render_ls_elza_dialog_markup()

    rendered = ui.render_ls_elza_assets(
        "library",
        view_context={},
        docked=False,
        local_family_title="",
        app_version="v2.28",
        opacity=50,
    )

    assert 'shell.setAttribute("data-elza-v232", "composer")' in rendered
    assert "UX pārbaude" in rendered
    assert "Testēt funkciju" in rendered
    assert "Track analīze" in rendered
    assert "Koda analīze" in rendered
    assert "Balss" in rendered
    assert "createAnalyser" in rendered
    assert "getByteFrequencyData" in rendered

    enhancer_source = Path("LS_Elza/v230_ui_enhancer.py").read_text(encoding="utf-8")
    assert "@keyframes" not in enhancer_source


def test_elza_v232_stt_source_contract():
    service_source = Path("LS_Elza/service.py").read_text(encoding="utf-8")
    controller_source = Path("ls_web/elza_controller.py").read_text(encoding="utf-8")

    compile(service_source, "LS_Elza/service.py", "exec")
    compile(controller_source, "ls_web/elza_controller.py", "exec")

    assert 'DEFAULT_STT_MODEL = "gpt-4o-mini-transcribe"' in service_source
    assert "def transcribe_ls_elza_audio" in service_source
    assert 'language="lv"' in service_source
    assert 'if path == "/ls-elza-stt":' in controller_source
    assert "def ls_elza_stt" in controller_source
    assert "transcribe_ls_elza_audio" in controller_source


def _v238_model_input(question):
    return [{
        "role": "user",
        "content": (
            "Current read-only LocalSunoDb context:\n{}"
            "\n\nUser question:\n" + question
        ),
    }]


def _v238_wrong_model_selection():
    return {
        "safe_to_execute": True,
        "reason": "",
        "category": "Song",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "",
        "local_audio": "",
        "local_audio_extensions": [],
        "exclude_ui_types": [],
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": True,
        "title_query": "",
        "anywhere_query": "",
        "exact_stem_count": 0,
    }


def test_elza_v238_repairs_exact_user_local_anywhere_request():
    question = (
        'Parādi visas vietējās dziesmas, kurām "upe" ir '
        'nosaukumā vai kur citur.'
    )
    result = selection_guard.reconcile_selection_tool_arguments(
        "ls_prepare_selection",
        _v238_wrong_model_selection(),
        _v238_model_input(question),
    )

    assert result["local_family"] == ""
    assert result["local_family_assigned"] is None
    assert result["local_audio"] == "with"
    assert result["category"] == ""
    assert result["title_query"] == ""
    assert result["anywhere_query"] == "upe"


def test_elza_v238_keeps_explicit_locf_request():
    original = _v238_wrong_model_selection()
    result = selection_guard.reconcile_selection_tool_arguments(
        "ls_prepare_selection",
        original,
        _v238_model_input("Parādi visas dziesmas ar LocF."),
    )

    assert result["local_family_assigned"] is True


def test_elza_v238_keeps_non_selection_tools_untouched():
    original = {"local_family_assigned": True}
    result = selection_guard.reconcile_selection_tool_arguments(
        "ls_search_titles",
        original,
        _v238_model_input(
            'Parādi visas vietējās dziesmas, kurām "upe" ir nosaukumā vai kur citur.'
        ),
    )
    assert result == original
