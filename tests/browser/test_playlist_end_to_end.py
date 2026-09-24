import json
import sys
import traceback
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "browser-artifacts"
BASE_URL = "http://127.0.0.1:8765"


def playlist_json():
    with urlopen(BASE_URL + "/playlists-json", timeout=5) as response:
        return json.load(response)


def write_failure(page, console_messages, page_errors):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(ARTIFACTS / "playlist-e2e-failure.png"), full_page=True)
    except Exception:
        pass
    state = {}
    try:
        state = page.evaluate(
            """() => ({
              href: location.href,
              title: document.title,
              visibleRows: Array.from(document.querySelectorAll('tr.track-row')).filter(row => {
                const style = getComputedStyle(row);
                const rect = row.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 0;
              }).map(row => row.dataset.trackId),
              checked: Array.from(document.querySelectorAll('.track-check:checked')).map(el => el.value),
              f4Display: document.getElementById('finder-search-box')?.style.display || '',
              playlistRows: Array.from(document.querySelectorAll('.playlist-track-row')).map(row => row.dataset.trackId),
              playlistAudio: document.getElementById('playlist-audio')?.src || ''
            })"""
        )
    except Exception as exc:
        state = {"diagnostic_error": str(exc)}
    (ARTIFACTS / "playlist-e2e-diagnostics.json").write_text(
        json.dumps(
            {"state": state, "console": console_messages, "page_errors": page_errors},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def visible_library_ids(page):
    return page.locator("tr.track-row").evaluate_all(
        """rows => rows.filter(row => {
          const style = getComputedStyle(row);
          const rect = row.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 0;
        }).map(row => row.dataset.trackId)"""
    )


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    console_messages = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1900, "height": 900})
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=30000)
            page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)

            # Contract: default Library order is newest first.
            ids = visible_library_ids(page)
            assert ids[:3] == ["browser-3", "browser-2", "browser-1"], ids

            # Contract: F4 opens Finder search.
            page.keyboard.press("F4")
            finder = page.locator("#finder-search-box")
            finder.wait_for(state="visible", timeout=3000)
            page.wait_for_function(
                "() => document.getElementById('finder-search-input') === document.activeElement",
                timeout=1500,
            )
            page.keyboard.press("Escape")

            # Select newest track from its Cover circle and add to Vārda diena.
            newest_row = page.locator('tr.track-row[data-track-id="browser-3"]')
            newest_row.locator(".ls-track-select-control").click()
            page.wait_for_function(
                "() => document.getElementById('audio-playlist-select')?.classList.contains('is-enabled')",
                timeout=3000,
            )
            page.locator("#audio-playlist-summary").click()
            name_day = page.get_by_role("menuitem", name="Vārda diena (7)", exact=True)
            name_day.wait_for(state="visible", timeout=3000)
            page.once("dialog", lambda dialog: dialog.accept())
            name_day.click()
            page.wait_for_timeout(250)

            # Contract: selection clears visually and from stored UI state after add.
            assert page.locator(".track-check:checked").count() == 0
            assert not newest_row.locator(".track-check").is_checked()
            assert page.locator("#audio-playlist-summary").get_attribute("aria-disabled") == "true"

            data = playlist_json()
            target = next(item for item in data["playlists"] if item["name"] == "Vārda diena")
            assert target["track_count"] == 8, target
            assert target["track_ids"][0] == "browser-3", target["track_ids"]

            # Open Playlist and prove the newly added track is first.
            page.get_by_role("link", name="Playlists", exact=True).click()
            page.get_by_role("link", name="Vārda diena", exact=False).first.click()
            page.locator(".playlist-track-row").first.wait_for(state="visible", timeout=5000)
            playlist_ids = page.locator(".playlist-track-row").evaluate_all(
                "rows => rows.map(row => row.dataset.trackId)"
            )
            assert playlist_ids[0] == "browser-3", playlist_ids

            # Contract: row Play and Play All point at a real local playback endpoint.
            audio = page.locator("#playlist-audio")
            row_play = page.locator('.playlist-track-row[data-track-id="browser-3"] .playlist-track-play')
            row_play.click()
            page.wait_for_function(
                "() => document.getElementById('playlist-audio')?.getAttribute('src')?.includes('track_id=browser-3')",
                timeout=3000,
            )
            row_src = audio.get_attribute("src") or ""
            assert "track_id=browser-3" in row_src, row_src
            assert "source=local" in row_src, row_src
            row_response = page.request.get(BASE_URL + row_src)
            assert row_response.ok, (row_response.status, row_src)

            audio.evaluate("el => { el.pause(); el.removeAttribute('src'); el.load(); }")
            page.locator("#playlist-play-all").click()
            page.wait_for_function(
                "() => document.getElementById('playlist-audio')?.getAttribute('src')?.includes('track_id=browser-3')",
                timeout=3000,
            )
            all_src = audio.get_attribute("src") or ""
            assert "track_id=browser-3" in all_src, all_src
            assert "source=local" in all_src, all_src
            all_response = page.request.get(BASE_URL + all_src)
            assert all_response.ok, (all_response.status, all_src)

            # Contract: returning to Library does not require F5 and rows are immediately present.
            page.get_by_role("link", name="Suno Library", exact=True).click()
            page.locator("tr.track-row").first.wait_for(state="visible", timeout=5000)
            ids_after_return = visible_library_ids(page)
            assert ids_after_return[:3] == ["browser-3", "browser-2", "browser-1"], ids_after_return

            # F4 must still work after returning from Playlist.
            page.keyboard.press("F4")
            page.locator("#finder-search-box").wait_for(state="visible", timeout=3000)

            assert not page_errors, page_errors
            page.screenshot(path=str(ARTIFACTS / "playlist-e2e-success.png"), full_page=True)
        except Exception:
            write_failure(page, console_messages, page_errors)
            traceback.print_exc()
            browser.close()
            return 1

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
