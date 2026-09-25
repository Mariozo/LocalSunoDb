import json
import shutil
import sys
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:8765"
AUDIO_ROOT = ROOT / "Temp" / "fresh-install-audio"
MUSIC_ROOT = ROOT / "Temp" / "fresh-install-music"


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
    if MUSIC_ROOT.exists():
        shutil.rmtree(MUSIC_ROOT)

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

    album = MUSIC_ROOT / "[1975] - Al Jarreau - We Got By"
    write_wav(album / "(01) - Al Jarreau - Spirit.wav")
    write_wav(album / "(02) - Al Jarreau - We Got By.wav")
    (album / "Folder.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"browser-cover" * 32)


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

        # Separate non-Suno music DB stays outside the canonical LocalSunoDb.
        page.locator("#music-db-name-input").fill("Jazz")
        page.locator("#music-db-genre-input").fill("Jazz")
        page.locator("#music-db-root-input").fill(str(MUSIC_ROOT))
        page.locator("#music-db-import").click()
        page.wait_for_function(
            "() => document.getElementById('music-db-status')?.textContent?.includes('Gatavs:')",
            timeout=20000,
        )
        db_button = page.locator("#music-db-list button", has_text="Jazz")
        db_button.wait_for(state="visible", timeout=5000)
        db_button.click()
        page.locator("#music-db-preview").wait_for(state="visible", timeout=5000)
        preview_text = page.locator("#music-db-preview").inner_text()
        assert "Al Jarreau" in preview_text, preview_text
        assert "1975" in preview_text, preview_text
        assert "We Got By" in preview_text, preview_text

        db_response = page.request.get(BASE_URL + "/music-db-list")
        assert db_response.ok, db_response.status
        databases = db_response.json()["databases"]
        jazz = next(item for item in databases if item["name"] == "Jazz")
        assert jazz["track_count"] == 2, jazz
        assert jazz["artist_count"] == 1, jazz
        assert jazz["cover_count"] == 1, jazz
        assert Path(jazz["root_folder"]) == MUSIC_ROOT

        # Re-scan is incremental and must not duplicate the catalog.
        page.locator("#music-db-import").click()
        page.wait_for_function(
            "() => document.getElementById('music-db-status')?.textContent?.includes('2 nemainītas')",
            timeout=20000,
        )

        assert not page_errors, page_errors
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
