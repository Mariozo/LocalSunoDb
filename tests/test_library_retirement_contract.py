from pathlib import Path


def test_retired_rows_on_screen_controls_do_not_return():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    settings_controller = Path("ls_web/settings_controller.py").read_text(encoding="utf-8")
    handler = Path("ls_web/handler.py").read_text(encoding="utf-8")

    retired_markers = (
        "default-rows-select",
        "save-default-rows-btn",
        "/set-default-rows",
        "default_rows",
    )
    combined = "\n".join((template, settings_controller, handler))

    for marker in retired_markers:
        assert marker not in combined


def test_library_keeps_v1_05_cursor_loading_contract():
    lazy_loader = Path(
        "ls_library/static/suno_library_lazy_loader.js"
    ).read_text(encoding="utf-8")
    handler = Path("ls_web/handler.py").read_text(encoding="utf-8")

    assert "const BATCH_SIZE = 32;" in lazy_loader
    assert 'return "/library-rows?"' in lazy_loader
    assert 'return "/library-count?"' in lazy_loader
    assert 'if path == "/library-rows":' in handler
    assert 'if path == "/library-count":' in handler
    assert 'cursor=params.get("cursor", [""])[0]' in handler
