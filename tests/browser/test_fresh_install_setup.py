import json
import shutil
import sys
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:8765"
AUDIO_ROOT = ROOT / "Temp" / "fresh-install-audio"


def write_wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48000)
        wav_file.writeframes(b"\x00\x00\x00\x00" * 2400)


def prepare_audio_fixture():
    if AUDIO_ROOT.exists():
        shutil.rmtree(AUDIO_ROOT)
    write_wav(AUDIO_ROOT / "Loose Track.wav")
    write_wav(AUDIO_ROOT / "Song" / "Family One" / "1" / "Family One.wav")
    write_wav(
        AUDIO_ROOT
        / "Song"
        / "Family One"
        / "1"
        / "Stems"
        / "Family One (Vocals).wav"
    )


def main():
    prepare_audio_fixture()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page_errors = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=30000)

        modal = page.locator("#fresh-install-modal")
        modal.wait_for(state="visible", timeout=10000)
        assert "DB gatava:" in page.locator("#fresh-install-db-status").inner_text()

        root_input = page.locator("#fresh-install-root-input")
        root_input.fill(str(AUDIO_ROOT))
        page.locator("#fresh-install-import").click()

        page.wait_for_function(
            "() => document.getElementById('fresh-install-status')?.textContent?.includes('Gatavs.')",
            timeout=20000,
        )

        page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)
        modal.wait_for(state="hidden", timeout=10000)

        response = page.request.get(BASE_URL + "/fresh-install-state")
        assert response.ok, response.status
        state = response.json()
        assert state["setup_complete"] is True, state
        assert state["needs_setup"] is False, state
        assert state["track_count"] == 2, state
        assert state["media_count"] == 3, state
        assert Path(state["audio_library_root_folder"]) == AUDIO_ROOT

        titles = page.locator("tr.track-row").evaluate_all(
            "rows => rows.map(row => row.textContent || '')"
        )
        joined = "\n".join(titles)
        assert "Loose Track" in joined, joined
        assert "Family One" in joined, joined

        page.locator("#ls-sidebar-tools-trigger").click()
        setup_button = page.locator("#open-fresh-install-setup-btn")
        setup_button.wait_for(state="visible", timeout=3000)
        setup_button.click()
        modal.wait_for(state="visible", timeout=3000)
        assert "2 dziesmas" in page.locator("#fresh-install-db-status").inner_text()

        assert not page_errors, page_errors
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
