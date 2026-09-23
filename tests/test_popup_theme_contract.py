from pathlib import Path
import re

from ls_web import render as web_render


ROOT = Path(__file__).resolve().parents[1]
POPUP_CSS_PATH = ROOT / "ls_web" / "static" / "popup_theme.css"
LIBRARY_TEMPLATE_PATH = ROOT / "ls_library" / "templates" / "library.html"


def _css_block(css, selector):
    pattern = re.compile(re.escape(selector) + r"\s*\{(?P<body>.*?)\}", re.S)
    match = pattern.search(css)
    assert match is not None, f"Missing CSS block: {selector}"
    return match.group("body")


def test_popup_theme_contract_covers_all_popup_families_and_loads_last():
    style_block = web_render.render_suno_page_style_block()
    deferred_assets = web_render.render_ls_popup_theme_assets()
    popup_css = POPUP_CSS_PATH.read_text(encoding="utf-8")
    template = LIBRARY_TEMPLATE_PATH.read_text(encoding="utf-8")

    stylesheet_urls = re.findall(r'<link[^>]+href="([^"]+)"', style_block)
    assert stylesheet_urls
    assert stylesheet_urls[-1].split("?", 1)[0].endswith("/ls_web/static/popup_theme.css")
    assert "ls_web/static/popup_theme.css" not in deferred_assets

    shared_surface_targets = (
        ".modal",
        ".wav-preview-modal",
        ".wav-result-modal",
        ".compare-this-modal",
        ".busy-box",
        ".ls-refresh-box",
        ".user-tag-panel",
        ".ls-popup-dialog",
    )
    surface_group = popup_css.split(".modal h1", 1)[0]
    for selector in shared_surface_targets:
        assert selector in surface_group

    critical_selectors = (
        "#ls-library #settings-modal > .modal",
        "#ls-library #stats-modal > .ls-stats-modal-card",
        "#ls-library #help-modal > .modal",
        "#ls-library #user-tag-panel.user-tag-panel",
    )
    for selector in critical_selectors:
        assert selector in popup_css

    finder_block = _css_block(popup_css, ".finder-search-box")
    assert "background: var(--ls-popup-surface) !important;" in finder_block
    assert "color: var(--ls-popup-text) !important;" in finder_block

    elza_block = _css_block(popup_css, ".ls-elza-dialog")
    assert "background:" in elza_block and "!important" in elza_block
    assert "color: var(--ls-popup-text) !important;" in elza_block

    for element_id in (
        "settings-modal",
        "stats-modal",
        "help-modal",
        "user-tag-panel",
        "finder-search-box",
    ):
        assert f'id="{element_id}"' in template
