from pathlib import Path


def test_imports_secondary_sidebar_shows_version_token():
    template = Path("ls_web/templates/secondary_sidebar.html").read_text(
        encoding="utf-8"
    )
    assert '<span class="ls-sidebar-title-full">LS @@LS0@@</span>' in template


def test_imports_main_heading_is_not_duplicating_version():
    template = Path("ls_downloader/templates/downloader.html").read_text(
        encoding="utf-8"
    )
    assert "<h1>Imports</h1>" in template
    assert "Imports <span class=\"muted\">· LS" not in template


def test_restored_expired_token_401_is_cleared_from_dom_only_on_restore():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")

    assert "function isHistoricalExpiredSunoTokenStatus(statusText)" in script
    assert "else if (isHistoricalExpiredSunoTokenStatus(metaStatus.innerText))" in script
    assert 'metaStatus.innerText = "Gatavs."' in script

    # New live errors still use setStatus elsewhere; this patch only touches restore logic.
    restore_start = script.index("async function restoreDownloaderState()")
    restore_end = script.index("function markDownloaderViewFresh()", restore_start)
    restore_block = script[restore_start:restore_end]
    assert "isHistoricalExpiredSunoTokenStatus(metaStatus.innerText)" in restore_block
