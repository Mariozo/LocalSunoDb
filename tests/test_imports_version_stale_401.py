from pathlib import Path


def test_imports_header_shows_app_version_token():
    template = Path("ls_downloader/templates/downloader.html").read_text(
        encoding="utf-8"
    )
    assert '<h1>Imports <span class="muted">· LS @@LS0@@</span></h1>' in template


def test_downloader_state_filters_only_historical_expired_token_401():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")

    assert "function isHistoricalExpiredSunoTokenStatus(statusText)" in script
    assert "/Suno API HTTP 401/i.test(text)" in script
    assert "token is expired" in script
    assert "token is invalid" in script
    assert "Renew Suno login" in script
    assert 'status_text: staleAuthStatus ? "" : statusText' in script
    assert 'status_mode: staleAuthStatus ? "" :' in script


def test_general_401_statuses_are_not_globally_suppressed():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")

    assert "HTTP 401" not in script.replace("Suno API HTTP 401", "")
    assert "isHistoricalExpiredSunoTokenStatus" in script
