import sqlite3
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "browser-artifacts"
BASE_URL = "http://127.0.0.1:8765"
DB_PATH = ROOT / "Data" / "local_suno.db"


def prepare_fixture():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE tracks SET kind='Upload' WHERE id='browser-2'"
        )
        conn.commit()
    finally:
        conn.close()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    prepare_fixture()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})

        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=30000)
            page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)

            version_label = page.locator(".ls-sidebar-title-full")
            version_label.wait_for(state="visible", timeout=5000)
            assert version_label.inner_text().strip() == "LS v2.24"

            page.locator("#ls-elza-open-btn").click()
            page.locator("#ls-elza-input").fill(
                "Parādi viaus lokālos Wav bez Uplod."
            )
            page.locator("#ls-elza-send").click()

            assistant = page.locator(".ls-elza-message-assistant").last
            assistant.wait_for(state="visible", timeout=10000)
            text = assistant.inner_text()

            assert "Atrasti **2 ieraksti**" in text or "Atrasti 2 ieraksti" in text
            assert "Local WAV" in text
            assert "Bez Type: Upload" in text

            button = assistant.locator(
                '[data-ls-elza-action="open-view"]'
            )
            button.wait_for(state="visible", timeout=5000)
            assert button.inner_text().strip() == "Atvērt atlasi LS"

            button.click()
            page.wait_for_url(
                lambda url: "track_ids=" in str(url),
                timeout=10000,
            )
            href = page.url

            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            track_ids = ",".join(query.get("track_ids", [])).split(",")
            track_ids = [item for item in track_ids if item]

            assert "browser-1" in track_ids
            assert "browser-3" in track_ids
            assert "browser-2" not in track_ids
            assert query.get("rows") == ["all"]

            page.screenshot(
                path=str(ARTIFACTS / "elza-ask-selection-success.png"),
                full_page=True,
            )
        except Exception:
            try:
                page.screenshot(
                    path=str(ARTIFACTS / "elza-ask-selection-failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            traceback.print_exc()
            browser.close()
            return 1

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
