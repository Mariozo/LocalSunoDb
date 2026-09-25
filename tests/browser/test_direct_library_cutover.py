import json
import sys
import traceback
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "browser-artifacts"
BASE_URL = "http://127.0.0.1:8765"


def row_ids(page):
    return page.locator("tr.track-row").evaluate_all(
        "(rows) => rows.map((row) => row.dataset.trackId)"
    )


def wait_rows(page):
    page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)
    page.wait_for_function(
        "() => document.getElementById('ls-filter-result-count')?.dataset?.state === 'ready'",
        timeout=10000,
    )


def open_view(page, params=None):
    query = ("?" + urlencode(params, doseq=True)) if params else ""
    page.goto(BASE_URL + "/" + query, wait_until="domcontentloaded", timeout=30000)
    wait_rows(page)


def request_count(page, params=None):
    query = ("?" + urlencode(params or {}, doseq=True)) if params else ""
    response = page.request.get(BASE_URL + "/library-count" + query)
    assert response.ok, (response.status, response.text())
    payload = response.json()
    assert payload["ok"] is True, payload
    return int(payload["total"])


def request_rows(page, params=None):
    payload_params = dict(params or {})
    payload_params["batch"] = "100"
    query = "?" + urlencode(payload_params, doseq=True)
    response = page.request.get(BASE_URL + "/library-rows" + query)
    assert response.ok, (response.status, response.text())
    payload = response.json()
    assert payload["ok"] is True, payload
    return payload


def assert_count_matches_rows(page, params):
    count = request_count(page, params)
    payload = request_rows(page, params)
    assert payload["loaded"] == count, (params, count, payload["loaded"])
    return count


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    console_messages = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1900, "height": 1000})
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            open_view(page)
            assert page.title() == "LS v2.27.1"
            assert request_count(page) == 75
            assert "75 tracks" in page.locator("#ls-filter-result-count").inner_text()

            # Text search.
            open_view(page, {"q": "Alpha Search"})
            assert row_ids(page) == ["canon-001"]
            assert_count_matches_rows(page, {"q": "Alpha Search"}) == 1

            # Category: track_user.manual_category overrides tracks.kind.
            params = {"q": "Manual Category", "category_filter": "Instrumental"}
            open_view(page, params)
            assert row_ids(page) == ["canon-002"]
            assert page.locator("tr.track-row").first.get_attribute("data-main-category") == "Instrumental"
            assert_count_matches_rows(page, params) == 1

            # Broad Song / Instrumental category filters use the same canonical
            # category contract on the real browser path.
            params = {"category_filter": "Song"}
            open_view(page, params)
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-main-category") == "Song"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 38

            params = {"category_filter": "Instrumental"}
            open_view(page, params)
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-main-category") == "Instrumental"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 37

            # Type comes from tracks.source_task, not Category.
            params = {"kind_filter": "Cover"}
            open_view(page, params)
            rows = page.locator("tr.track-row")
            assert rows.count() > 0
            assert all(
                rows.nth(i).get_attribute("data-kind") == "Cover"
                for i in range(rows.count())
            )
            assert_count_matches_rows(page, params) == 25

            # Liked is canonical tracks.is_liked.
            params = {"kind_filter": "__liked__"}
            open_view(page, params)
            assert page.locator(".like-toggle-btn.liked").count() == page.locator("tr.track-row").count()
            assert_count_matches_rows(page, params) > 3

            # Flags: one flag and a required combination.
            params = {"flag_filter": "1"}
            open_view(page, params)
            assert set(row_ids(page)) >= {"canon-001", "canon-002"}
            assert_count_matches_rows(page, params) == 2

            params = {"flag_filter": "1,4"}
            open_view(page, params)
            assert row_ids(page) == ["canon-001"]
            assert_count_matches_rows(page, params) == 1

            # Exact tag.
            params = {"tag_filter": "#rock"}
            open_view(page, params)
            assert set(row_ids(page)) == {"canon-001", "canon-002"}
            assert_count_matches_rows(page, params) == 2

            # Workspace.
            params = {"workspace": "Studio B"}
            open_view(page, params)
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-workspace") == "Studio B"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 25

            # Local / Suno source split uses canonical variants + media_files.
            params = {"local_audio_filter": "with"}
            open_view(page, params)
            assert all(
                page.locator("tr.track-row .play-btn").nth(i).get_attribute("data-has-local-audio") == "true"
                for i in range(page.locator("tr.track-row .play-btn").count())
            )
            local_count = assert_count_matches_rows(page, params)
            assert local_count == 26

            params = {"local_audio_filter": "without"}
            open_view(page, params)
            assert all(
                page.locator("tr.track-row .play-btn").nth(i).get_attribute("data-has-local-audio") == "false"
                for i in range(page.locator("tr.track-row .play-btn").count())
            )
            assert_count_matches_rows(page, params) == 49

            # Sorts are server-side canonical values.
            open_view(page, {"sort_by": "title", "sort_dir": "asc"})
            assert row_ids(page)[0] == "canon-001"
            open_view(page, {"sort_by": "created", "sort_dir": "desc"})
            created_ids = row_ids(page)
            assert created_ids[0] != created_ids[-1]
            open_view(page, {"sort_by": "duration", "sort_dir": "desc"})
            assert row_ids(page)[0] == "canon-075"

            # Real lazy-loading path: first 32, then normal page scrolling
            # must trigger cursor batches to all 75. Do not call the test hook.
            open_view(page, {"sort_by": "title", "sort_dir": "asc"})
            page.wait_for_function(
                "() => window.LSLibraryLazyState && window.LSLibraryLazyState().loadedCount >= 32",
                timeout=10000,
            )
            while page.evaluate("() => window.LSLibraryLazyState().hasMore"):
                before = len(row_ids(page))
                before_geometry = page.evaluate("""() => {
                    const root = document.querySelector("main");
                    const sentinel = document.getElementById("library-lazy-sentinel");
                    const rr = root.getBoundingClientRect();
                    const sr = sentinel.getBoundingClientRect();
                    return {
                        state: window.LSLibraryLazyState(),
                        scrollTop: root.scrollTop,
                        scrollHeight: root.scrollHeight,
                        clientHeight: root.clientHeight,
                        rootTop: rr.top,
                        rootBottom: rr.bottom,
                        sentinelTop: sr.top,
                        sentinelBottom: sr.bottom,
                        sentinelHidden: sentinel.hidden
                    };
                }""")
                print("LAZY_BEFORE", json.dumps(before_geometry, sort_keys=True))
                page.locator("#library-lazy-sentinel").scroll_into_view_if_needed(timeout=5000)
                after_geometry = page.evaluate("""() => {
                    const root = document.querySelector("main");
                    const sentinel = document.getElementById("library-lazy-sentinel");
                    const rr = root.getBoundingClientRect();
                    const sr = sentinel.getBoundingClientRect();
                    return {
                        state: window.LSLibraryLazyState(),
                        scrollTop: root.scrollTop,
                        scrollHeight: root.scrollHeight,
                        clientHeight: root.clientHeight,
                        rootTop: rr.top,
                        rootBottom: rr.bottom,
                        sentinelTop: sr.top,
                        sentinelBottom: sr.bottom,
                        sentinelHidden: sentinel.hidden
                    };
                }""")
                print("LAZY_AFTER", json.dumps(after_geometry, sort_keys=True))
                page.wait_for_function(
                    "(n) => window.LSLibraryLazyState().loadedCount > n || !window.LSLibraryLazyState().hasMore",
                    arg=before,
                    timeout=10000,
                )
            loaded_ids = row_ids(page)
            assert len(loaded_ids) == 75
            assert len(set(loaded_ids)) == 75

            # Local playback URL and actual media response use canonical linkage.
            open_view(page, {"q": "Alpha Search"})
            play = page.locator("tr.track-row .play-btn").first
            assert play.get_attribute("data-has-local-audio") == "true"
            local_url = play.get_attribute("data-local-audio")
            assert local_url and local_url.startswith("/local-audio?track_id=")
            media_response = page.request.get(BASE_URL + local_url)
            assert media_response.ok, media_response.status
            assert "audio" in (media_response.headers.get("content-type") or "").lower()

            # Stem count comes from canonical media_files role='stem'.
            assert "Stems 1" in page.locator("tr.track-row").first.inner_text()

            assert not page_errors, "Browser page errors: " + " | ".join(page_errors)
            (ARTIFACTS / "direct-library-console.txt").write_text(
                "\n".join(console_messages) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(ARTIFACTS / "direct-library-success.png"),
                full_page=True,
            )
        except Exception:
            try:
                page.screenshot(
                    path=str(ARTIFACTS / "direct-library-failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            (ARTIFACTS / "direct-library-errors.json").write_text(
                json.dumps(
                    {"console": console_messages, "page_errors": page_errors},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            traceback.print_exc()
            browser.close()
            return 1

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
