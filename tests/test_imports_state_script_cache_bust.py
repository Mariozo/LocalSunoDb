from pathlib import Path


def test_downloader_state_script_has_explicit_cache_bust():
    render = Path("ls_downloader/render.py").read_text(encoding="utf-8")
    assert "downloader_state_script.js" in render
    assert "&rev=imports-state-cache-bust-1" in render


def test_stale_401_fix_is_still_in_state_script():
    script = Path(
        "ls_downloader/static/downloader_state_script.js"
    ).read_text(encoding="utf-8")
    assert "isHistoricalExpiredSunoTokenStatus" in script
    assert "isHistoricalExpiredSunoTokenStatus(metaStatus.innerText)" in script
