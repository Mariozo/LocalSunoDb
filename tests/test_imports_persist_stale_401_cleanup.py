from pathlib import Path


def test_stale_401_cleanup_is_persisted_to_browser_and_server():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")

    assert "isHistoricalExpiredSunoTokenStatus(rawState.status_text)" in script
    assert "writeDownloaderStateToBrowser(normalized);" in script
    assert "await writeDownloaderStateToServer(normalized);" in script


def test_state_script_revision_is_advanced():
    render = Path("ls_downloader/render.py").read_text(encoding="utf-8")
    assert "&rev=imports-state-cache-bust-2" in render
    assert "&rev=imports-state-cache-bust-1" not in render


def test_stale_401_match_stays_narrow():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")

    assert "/Suno API HTTP 401/i.test(text)" in script
    assert "token is expired" in script
    assert "token is invalid" in script
    assert "Renew Suno login" in script
