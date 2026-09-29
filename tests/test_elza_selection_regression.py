import json
from io import BytesIO
from pathlib import Path

from LS_Elza import LS_ELZA_PACKAGE_VERSION, selection_intent, ui
from LS_Elza import selection_guard
from ls_web import elza_adapter
from ls_web import elza_selftest
from ls_web import elza_selection_bridge
from ls_web import elza_controller


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
    assert LS_ELZA_PACKAGE_VERSION == "2.47"
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



def test_elza_v240_voice_composer_contract():
    assert LS_ELZA_PACKAGE_VERSION == "2.47"
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


def test_elza_v240_prompt_only_is_deterministic_and_not_locf():
    result = elza_selection_bridge._recognize_local_text_selection(
        'Parādi dziesmas ar vārdu "fretless" Promptā.'
    )
    assert result is not None
    assert result["local_family_assigned"] is None
    assert result["category"] == ""
    assert result["text_query"] == "fretless"
    assert result["text_fields"] == ["prompt"]


def test_elza_v240_hammond_all_explicit_fields_is_not_locf():
    result = elza_selection_bridge._recognize_local_text_selection(
        'Parādi visas dziesmas ar vārdu "Hammond" Promta laukā vai '
        'Name/Track ID, Lyrics un Tags laukos'
    )
    assert result is not None
    assert result["local_family_assigned"] is None
    assert result["category"] == ""
    assert result["text_query"] == "Hammond"
    assert set(result["text_fields"]) == {
        "name", "track_id", "lyrics", "prompt", "tags",
    }
    assert result["anywhere_query"] == "Hammond"


def test_elza_v240_local_anywhere_means_local_audio_not_locf():
    result = elza_selection_bridge._recognize_local_text_selection(
        'Parādi visas vietējās dziesmas, kurām "upe" ir nosaukumā vai kur citur.'
    )
    assert result is not None
    assert result["local_audio"] == "with"
    assert result["local_family_assigned"] is None
    assert result["category"] == ""
    assert result["text_query"] == "upe"
    assert set(result["text_fields"]) == {
        "name", "track_id", "lyrics", "prompt", "tags",
    }


def test_elza_v240_plain_local_tracks_do_not_become_locf():
    result = elza_selection_bridge._recognize_local_text_selection(
        "Parādi visas vietējās dziesmas."
    )
    assert result is not None
    assert result["local_audio"] == "with"
    assert result["local_family_assigned"] is None
    assert result["text_query"] == ""
    assert result["text_fields"] == []


def test_elza_v240_explicit_locf_still_uses_locf_path():
    result = elza_selection_bridge.prepare_local_locf_service_result({
        "action": "send",
        "message": "Parādi visas dziesmas ar LocF.",
        "selected_mode": "",
        "images": [],
    })
    assert result is not None
    assert result["selection_request"]["local_family_assigned"] is True


def test_elza_v240_prompt_only_execution_filters_prompt(monkeypatch):
    rows = [
        {
            "id": "title-hit",
            "title": "fretless title",
            "workspace": "W",
            "lyrics": "",
            "prompt": "",
            "user_tags": "",
        },
        {
            "id": "prompt-hit",
            "title": "Other",
            "workspace": "W",
            "lyrics": "",
            "prompt": "warm fretless bass",
            "user_tags": "",
        },
        {
            "id": "lyrics-hit",
            "title": "Other 2",
            "workspace": "W",
            "lyrics": "fretless line",
            "prompt": "",
            "user_tags": "",
        },
    ]
    monkeypatch.setattr(elza_adapter, "search_tracks", lambda **_kwargs: rows, raising=False)

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {},
        "text_query": "fretless",
        "text_fields": ["prompt"],
        "summary": "Prompt: fretless",
        "save_name": "Prompt: fretless",
    }, limit=20)

    assert result["matched_count"] == 1
    assert "prompt-hit" in result["view_url"]
    assert "title-hit" not in result["view_url"]
    assert "lyrics-hit" not in result["view_url"]


def test_elza_v240_all_text_fields_do_not_return_unmatched_library(monkeypatch):
    rows = [
        {
            "id": "name-hit",
            "title": "Hammond B3",
            "workspace": "W",
            "lyrics": "",
            "prompt": "",
            "user_tags": "",
        },
        {
            "id": "prompt-hit",
            "title": "Other",
            "workspace": "W",
            "lyrics": "",
            "prompt": "Hammond organ",
            "user_tags": "",
        },
        {
            "id": "tag-hit",
            "title": "Third",
            "workspace": "W",
            "lyrics": "",
            "prompt": "",
            "user_tags": "#Hammond",
        },
        {
            "id": "no-hit",
            "title": "Piano",
            "workspace": "W",
            "lyrics": "",
            "prompt": "grand piano",
            "user_tags": "#jazz",
        },
    ]
    monkeypatch.setattr(elza_adapter, "search_tracks", lambda **_kwargs: rows, raising=False)

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {},
        "text_query": "Hammond",
        "text_fields": ["name", "track_id", "lyrics", "prompt", "tags"],
        "summary": "Anywhere: Hammond",
        "save_name": "Anywhere: Hammond",
    }, limit=20)

    assert result["matched_count"] == 3
    assert "name-hit" in result["view_url"]
    assert "prompt-hit" in result["view_url"]
    assert "tag-hit" in result["view_url"]
    assert "no-hit" not in result["view_url"]


def test_elza_v240_guard_repairs_false_locf_and_exact_fields():
    result = selection_guard.reconcile_selection_tool_arguments(
        "ls_prepare_selection",
        _v238_wrong_model_selection(),
        _v238_model_input(
            'Parādi visas dziesmas ar vārdu "Hammond" Promta laukā vai '
            'Name/Track ID, Lyrics un Tags laukos'
        ),
    )
    assert result["local_family_assigned"] is None
    assert result["category"] == ""
    assert result["text_query"] == "Hammond"
    assert set(result["text_fields"]) == {
        "name", "track_id", "lyrics", "prompt", "tags",
    }

def test_elza_v240_controller_dispatches_name_prompt_anywhere_and_locf(monkeypatch):
    calls = []

    def fake_selection_result(intent, limit=20):
        calls.append(("selection", intent))
        return {"matched_count": 0}

    def fake_locf_result(assigned, intent, limit=20):
        calls.append(("locf", bool(assigned), intent))
        return {"matched_count": 0}

    monkeypatch.setattr(
        elza_controller,
        "get_ls_elza_selection_result",
        fake_selection_result,
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "get_ls_elza_exact_stem_result",
        lambda *_args, **_kwargs: {"matched_count": 0},
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "get_locf_selection_result",
        fake_locf_result,
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "build_ls_elza_selection_answer",
        lambda _result: "selection-ok",
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "build_locf_selection_answer",
        lambda _result: "locf-ok",
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "ls_elza_append_chat_exchange",
        lambda *_args, **_kwargs: {},
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "ls_elza_resolve_workspace",
        lambda value: value,
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "ls_elza_resolve_local_family",
        lambda value: value,
        raising=False,
    )
    monkeypatch.setattr(
        elza_controller,
        "normalize_tag_filter",
        lambda values: list(values or []),
        raising=False,
    )

    class DummyController(elza_controller.ElzaControllerMixin):
        def __init__(self, message):
            body = json.dumps({
                "action": "send",
                "message": message,
                "selected_mode": "",
                "images": [],
            }).encode("utf-8")
            self.headers = {"Content-Length": str(len(body))}
            self.rfile = BytesIO(body)
            self.sent = []

        def send_json_response(self, data, status=200):
            self.sent.append((status, data))

    cases = (
        (
            'Parādi dziesmas ar vārdu "Hammond" Name laukā.',
            "selection",
            ["name"],
        ),
        (
            'Parādi dziesmas ar vārdu "fretless" Promptā.',
            "selection",
            ["prompt"],
        ),
        (
            'Parādi visas vietējās dziesmas, kurām "upe" ir '
            'nosaukumā vai kur citur.',
            "selection",
            ["name", "track_id", "lyrics", "prompt", "tags"],
        ),
        (
            "Parādi visas dziesmas ar LocF.",
            "locf",
            None,
        ),
    )

    for message, expected_route, expected_fields in cases:
        calls.clear()
        controller = DummyController(message)
        controller.ls_assistant_chat()

        assert controller.sent
        status, response = controller.sent[-1]
        assert status == 200
        assert response["ok"] is True
        assert calls
        assert calls[0][0] == expected_route

        if expected_route == "selection":
            intent = calls[0][1]
            assert intent["local_family_assigned"] is None
            assert intent["text_fields"] == expected_fields
            assert response["answer"] == "selection-ok"
        else:
            assert calls[0][1] is True
            assert response["answer"] == "locf-ok"

def test_elza_v242_local_three_stars_and_like_preserves_all_conditions():
    question = (
        "Parādi man visas vietējās dziesmas, kurām ir "
        "vismaz trīs *** un Like"
    )
    service_result = elza_selection_bridge.prepare_local_locf_service_result({
        "action": "send",
        "message": question,
        "selected_mode": "",
        "images": [],
    })

    assert service_result is not None
    request = service_result["selection_request"]
    assert request["local_audio"] == "with"
    assert request["flags"] == []
    assert request["minimum_flag_count"] == 3
    assert request["exact_flags"] is False
    assert request["kind_filter"] == "liked"
    assert request["local_family_assigned"] is None

    intent = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda value: value,
        resolve_local_family=lambda value: value,
        normalize_tags=lambda values: list(values or []),
    )

    assert intent["filters"]["local_audio_filter"] == "with"
    assert intent["filters"]["kind_filter"] == "__liked__"
    assert "flag_filter" not in intent["filters"]
    assert intent["minimum_flag_count"] == 3
    assert "With local audio" in intent["summary"]
    assert "Liked" in intent["summary"]
    assert "Vismaz 3 ✶" in intent["summary"]


def test_elza_v242_minimum_three_flags_counts_enabled_bits(monkeypatch):
    rows = [
        {"id": "one", "title": "One", "workspace": "W", "user_marks": 4, "ui_type": "Song"},
        {"id": "two", "title": "Two", "workspace": "W", "user_marks": 5, "ui_type": "Song"},
        {"id": "three", "title": "Three", "workspace": "W", "user_marks": 7, "ui_type": "Song"},
        {"id": "four", "title": "Four", "workspace": "W", "user_marks": 15, "ui_type": "Song"},
        {"id": "five", "title": "Five", "workspace": "W", "user_marks": 31, "ui_type": "Song"},
    ]
    monkeypatch.setattr(elza_adapter, "search_tracks", lambda **_kwargs: rows, raising=False)

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {
            "local_audio_filter": "with",
            "kind_filter": "__liked__",
        },
        "minimum_flag_count": 3,
        "summary": "With local audio + Liked + Vismaz 3 ✶",
        "save_name": "3 flags",
    }, limit=20)

    assert result["matched_count"] == 3
    assert "three" in result["view_url"]
    assert "four" in result["view_url"]
    assert "five" in result["view_url"]
    assert "one" not in result["view_url"]
    assert "two" not in result["view_url"]


def test_elza_v247_all_wav_upload_means_suno_plus_local():
    service_result = elza_selection_bridge.prepare_local_locf_service_result({
        "action": "send",
        "message": "Parādi visus .wav kas ir Upload.",
        "selected_mode": "",
        "images": [],
    })

    assert service_result is not None
    request = service_result["selection_request"]
    assert request["wav_scope"] == "all"
    assert request["local_audio_extensions"] == []
    assert request["include_ui_types"] == ["Upload"]
    assert request["exclude_ui_types"] == []

    intent = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda value: value,
        resolve_local_family=lambda value: value,
        normalize_tags=lambda values: list(values or []),
    )

    assert "local_audio_filter" not in intent["filters"]
    assert intent["wav_scope"] == "all"
    assert intent["local_audio_extensions"] == []
    assert intent["include_ui_types"] == ["Upload"]
    assert "WAV (Suno + Local)" in intent["summary"]
    assert "Type: Upload" in intent["summary"]


def test_elza_v247_local_wav_upload_stays_local_only():
    service_result = elza_selection_bridge.prepare_local_locf_service_result({
        "action": "send",
        "message": "Parādi local .wav kam ir pazīme Upload",
        "selected_mode": "",
        "images": [],
    })

    assert service_result is not None
    request = service_result["selection_request"]
    assert request["wav_scope"] == "local"
    assert request["local_audio_extensions"] == ["wav"]
    assert request["include_ui_types"] == ["Upload"]

    intent = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda value: value,
        resolve_local_family=lambda value: value,
        normalize_tags=lambda values: list(values or []),
    )

    assert intent["filters"]["local_audio_filter"] == "with"
    assert intent["wav_scope"] == "local"
    assert intent["local_audio_extensions"] == ["wav"]
    assert "Local WAV" in intent["summary"]
    assert "Type: Upload" in intent["summary"]


def test_elza_v247_all_wav_upload_accepts_suno_or_local(monkeypatch):
    rows = [
        {
            "id": "local-upload",
            "title": "Local Upload",
            "workspace": "W",
            "ui_type": "Upload",
            "kind": "Upload",
            "audio_url": "",
            "local_wav": r"E:\\Audio\\local.wav",
            "local_mp3": "",
            "ui_best_local_audio_path": r"E:\\Audio\\local.wav",
        },
        {
            "id": "suno-upload",
            "title": "Suno Upload",
            "workspace": "W",
            "ui_type": "Upload",
            "kind": "Upload",
            "audio_url": "https://cdn1.suno.ai/suno-upload.mp3",
            "local_wav": "",
            "local_mp3": "",
            "ui_best_local_audio_path": "",
        },
        {
            "id": "wrong-type",
            "title": "Wrong type",
            "workspace": "W",
            "ui_type": "Song",
            "kind": "Song",
            "audio_url": "https://cdn1.suno.ai/song.mp3",
            "local_wav": r"E:\\Audio\\song.wav",
            "local_mp3": "",
            "ui_best_local_audio_path": r"E:\\Audio\\song.wav",
        },
    ]
    monkeypatch.setattr(elza_adapter, "search_tracks", lambda **_kwargs: rows, raising=False)
    monkeypatch.setattr(
        elza_adapter,
        "_ls_elza_canonical_type_keys",
        lambda _ids: {
            "local-upload": {"upload"},
            "suno-upload": {"upload"},
            "wrong-type": {"song"},
        },
        raising=False,
    )

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {},
        "wav_scope": "all",
        "local_audio_extensions": [],
        "include_ui_types": ["Upload"],
        "summary": "WAV (Suno + Local) + Type: Upload",
        "save_name": "All WAV Upload",
    }, limit=20)

    assert result["matched_count"] == 2
    assert "local-upload" in result["view_url"]
    assert "suno-upload" in result["view_url"]
    assert "wrong-type" not in result["view_url"]


def test_elza_v247_local_wav_upload_execution_requires_local_wav(monkeypatch):
    rows = [
        {
            "id": "keep",
            "title": "Keep",
            "workspace": "W",
            "ui_type": "Upload",
            "kind": "Upload",
            "audio_url": "https://cdn1.suno.ai/keep.mp3",
            "local_wav": r"E:\\Audio\\keep.wav",
            "local_mp3": "",
            "ui_best_local_audio_path": r"E:\\Audio\\keep.wav",
        },
        {
            "id": "remote-only",
            "title": "Remote only",
            "workspace": "W",
            "ui_type": "Upload",
            "kind": "Upload",
            "audio_url": "https://cdn1.suno.ai/remote.mp3",
            "local_wav": "",
            "local_mp3": "",
            "ui_best_local_audio_path": "",
        },
    ]
    monkeypatch.setattr(elza_adapter, "search_tracks", lambda **_kwargs: rows, raising=False)
    monkeypatch.setattr(
        elza_adapter,
        "_ls_elza_canonical_type_keys",
        lambda _ids: {
            "keep": {"upload"},
            "remote-only": {"upload"},
        },
        raising=False,
    )

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {"local_audio_filter": "with"},
        "wav_scope": "local",
        "local_audio_extensions": ["wav"],
        "include_ui_types": ["Upload"],
        "summary": "Local WAV + Type: Upload",
        "save_name": "Local WAV Upload",
    }, limit=20)

    assert result["matched_count"] == 1
    assert "keep" in result["view_url"]
    assert "remote-only" not in result["view_url"]


def test_elza_v241_ui_preserves_chat_question_and_view_actions():
    source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")
    compile(source, "LS_Elza/ui.py", "exec")

    assert "chatSnapshotStoragePrefix" in source
    assert "viewActionStoragePrefix" in source
    assert "restoreStoredLsViewActions" in source
    assert "rememberLsViewAction" in source
    assert "pendingQuestionAnchor = message" in source
    assert "scrollQuestionIntoView(message)" in source
    assert "Ctrl+klikšķis = saglabāt jautājuma atlasi kā View" in source
    assert "Saruna nav izdzēsta" in source

    load_start = source.index("async function loadCurrentChat()")
    load_end = source.index("function localLsElzaUiAnswer", load_start)
    load_source = source[load_start:load_end]
    assert "renderMessages([])" not in load_source
    assert "loadChatSnapshot()" in load_source

def test_elza_v242_selection_contract_accepts_ui_type_and_minimum_flag_count():
    tool = selection_intent.get_selection_tool_definition()
    properties = tool["parameters"]["properties"]
    assert "include_ui_types" in properties
    assert "minimum_flag_count" in properties

    normalized = selection_intent.normalize_selection_request({
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "liked",
        "local_audio": "with",
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": None,
        "title_query": "",
        "exact_stem_count": 0,
        "local_audio_extensions": ["wav"],
        "exclude_ui_types": [],
        "include_ui_types": ["Upload"],
        "minimum_flag_count": 3,
    })

    assert normalized["include_ui_types"] == ["Upload"]
    assert normalized["minimum_flag_count"] == 3

def test_elza_v243_upload_uses_canonical_source_type(monkeypatch):
    rows = [
        {
            "id": "upload-wav",
            "title": "Upload WAV",
            "workspace": "W",
            "type": "",
            "kind": "",
            "local_wav": r"E:\\Audio\\upload.wav",
            "local_mp3": "",
            "ui_best_local_audio_path": r"E:\\Audio\\upload.wav",
        },
        {
            "id": "song-wav",
            "title": "Song WAV",
            "workspace": "W",
            "type": "",
            "kind": "",
            "local_wav": r"E:\\Audio\\song.wav",
            "local_mp3": "",
            "ui_best_local_audio_path": r"E:\\Audio\\song.wav",
        },
    ]
    monkeypatch.setattr(
        elza_adapter,
        "search_tracks",
        lambda **_kwargs: rows,
        raising=False,
    )
    monkeypatch.setattr(
        elza_adapter,
        "_ls_elza_canonical_type_keys",
        lambda _ids: {
            "upload-wav": {"upload"},
            "song-wav": {"gen", "song"},
        },
        raising=False,
    )

    result = elza_adapter.get_ls_elza_selection_result({
        "filters": {"local_audio_filter": "with"},
        "local_audio_extensions": ["wav"],
        "include_ui_types": ["Upload"],
        "summary": "Local WAV + Type: Upload",
        "save_name": "Local WAV Upload",
    }, limit=20)

    assert result["matched_count"] == 1
    assert "upload-wav" in result["view_url"]
    assert "song-wav" not in result["view_url"]


def test_elza_v244_test_mode_wires_selection_selftest_readonly():
    source = Path("LS_Elza/service.py").read_text(encoding="utf-8")
    compile(source, "LS_Elza/service.py", "exec")

    assert 'SELECTION_SELFTEST_TOOL_NAME = "ls_selection_selftest"' in source
    assert "def get_selection_selftest_tool_definition():" in source
    assert "def get_test_readonly_tools():" in source
    assert 'elif selected_mode == "TEST_REVIEW":\n        tools = get_test_readonly_tools()' in source
    assert "from ls_web.elza_selftest import run_selection_selftest" in source
    assert "return run_selection_selftest()" in source


def test_elza_v244_parser_selftest_cases_are_all_green():
    cases = elza_selftest._parser_cases()
    assert len(cases) == 8
    assert {item["id"] for item in cases} == {
        "parser_local_like_min3",
        "parser_wav_upload",
        "parser_local_wav_upload",
        "parser_wav_without_upload",
        "parser_name",
        "parser_prompt",
        "parser_anywhere",
        "parser_locf",
    }
    assert all(item["status"] == "PASS" for item in cases), cases


def test_elza_v244_selftest_flag_semantics_are_distinct():
    one_flag3 = {"marks": 4}
    three_flags = {"marks": 7}

    assert elza_selftest._required_flags(one_flag3, [3]) is True
    assert elza_selftest._marks_at_least(one_flag3, 3) is False
    assert elza_selftest._marks_at_least(three_flags, 3) is True

def test_elza_v244_test_mode_does_not_require_screen_share_for_selftest():
    source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")
    compile(source, "LS_Elza/ui.py", "exec")

    activation_marker = (
        'return;\n'
        '                }\n'
        '                if (buttonMode === "UX_REVIEW") {'
    )
    assert activation_marker in source
    assert "Pārbaudi atlases filtrus" in source
    assert "Ekrāns vajadzīgs tikai vizuālam testam." in source

def test_elza_v245_chat_network_and_question_anchor_contracts():
    source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")
    compile(source, "LS_Elza/ui.py", "exec")

    assert "overflow-anchor: none;" in source
    assert "function saveVisibleChatSnapshot()" in source
    assert "function chatDataContainsQuestion(data, question)" in source
    assert "async function reconcileAfterNetworkFailure(question)" in source
    assert "const reconciled = await reconcileAfterNetworkFailure(message);" in source
    assert "function pinQuestionInView(question)" in source
    assert "window.requestAnimationFrame(pin);" in source

    send_start = source.index("async function sendMessage()")
    call_start = source.index("const data = await callService(serviceAction", send_start)
    pre_call = source[send_start:call_start]
    assert 'addMessage("user", displayMessage);' in pre_call
    assert "saveVisibleChatSnapshot();" in pre_call

    reconcile_start = source.index("async function reconcileAfterNetworkFailure(question)")
    reconcile_end = source.index("async function loadCurrentChat()", reconcile_start)
    reconcile_source = source[reconcile_start:reconcile_end]
    assert "chatDataContainsQuestion(data, question)" in reconcile_source
    assert "applyChatData(data);" in reconcile_source
    assert reconcile_source.index("chatDataContainsQuestion(data, question)") < reconcile_source.index("applyChatData(data);")


def test_elza_v245_ctrl_click_is_connected_to_saved_views_and_uses_question_name():
    ui_source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")
    saved_view_source = Path(
        "ls_library/static/suno_saved_views_script_assets.js"
    ).read_text(encoding="utf-8")

    assert "event.ctrlKey || event.metaKey" in ui_source
    assert "dispatchLsViewSave(url, viewName)" in ui_source
    assert "latestUserQuestionText()" in ui_source
    assert "saglabāt jautājuma atlasi kā View" in ui_source

    assert 'window.addEventListener("ls-elza-save-view-request"' in saved_view_source
    assert "openSavedViewModal(" in saved_view_source
    assert 'window.dispatchEvent(new CustomEvent("ls-elza-view-saved"' in saved_view_source


def test_elza_v245_failed_fetch_keeps_local_snapshot_if_server_lacks_question():
    source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")

    helper_start = source.index("function chatDataContainsQuestion(data, question)")
    helper_end = source.index("async function reconcileAfterNetworkFailure(question)", helper_start)
    helper_source = source[helper_start:helper_end]
    assert 'message.role !== "user"' in helper_source
    assert 'content === targetText || content.startsWith(targetText + "\\n")' in helper_source

    catch_marker = 'if (/failed to fetch|networkerror|load failed/i.test(errorText)) {'
    catch_start = source.index(catch_marker)
    catch_end = source.index("} else {", catch_start)
    catch_source = source[catch_start:catch_end]
    assert "saveVisibleChatSnapshot();" in catch_source
    assert "reconcileAfterNetworkFailure(message)" in catch_source

def test_elza_v246_saved_view_preserves_exact_track_ids():
    source = Path(
        "ls_library/static/suno_saved_views_script_assets.js"
    ).read_text(encoding="utf-8")

    assert '"track_ids"' in source
    assert "const reusableQuery = buildReusableSavedViewQuery(sourceQuery);" in source
    assert "if (savedViewPendingQuery && !reusableQuery)" in source
    assert "filtrs pēc normalizēšanas ir tukšs" in source

def test_elza_v248_filter_ux_audit_is_bounded_test_tool():
    service_source = Path("LS_Elza/service.py").read_text(encoding="utf-8")
    ui_source = Path("LS_Elza/ui.py").read_text(encoding="utf-8")
    audit_source = Path("ls_web/elza_filter_audit.py").read_text(encoding="utf-8")

    compile(service_source, "LS_Elza/service.py", "exec")
    compile(ui_source, "LS_Elza/ui.py", "exec")
    compile(audit_source, "ls_web/elza_filter_audit.py", "exec")

    assert 'FILTER_UX_AUDIT_TOOL_NAME = "ls_filter_ux_audit"' in service_source
    assert "get_filter_ux_audit_tool_definition()" in service_source
    assert "run_filter_ux_audit" in service_source
    assert "Filter UX Audit" in service_source
    assert 'selectedMode === "TEST_REVIEW"' in ui_source
    assert "isFilterUxAuditRequest" in ui_source

    namespace = {}
    exec(audit_source, namespace)
    result = namespace["run_filter_ux_audit"]()
    assert result["read_only"] is True
    assert result["scope"] == "LocalSunoDb filter system"
    assert any(item["id"] == "workspace" for item in result["current_visible_controls"])
    assert any(item["id"] == "wav_scope" for item in result["elza_semantic_dimensions"])
    assert any("Upload" in item for item in result["known_interaction_constraints"])
    assert len(result["audit_requirements"]) >= 8
