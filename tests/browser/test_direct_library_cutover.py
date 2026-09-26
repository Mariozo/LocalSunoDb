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


def current_param(page, name):
    return page.evaluate(
        "(name) => new URL(window.location.href).searchParams.get(name)",
        name,
    )


def click_multi_filter(page, param, value):
    details = page.locator(f'details[data-multi-filter="{param}"]')
    details.locator("summary").click()
    option = page.locator(
        f'.library-multi-option[data-multi-filter-param="{param}"]'
        f'[data-multi-filter-value="{value}"]'
    )
    with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
        option.click()
    wait_rows(page)


def choose_auto_submit(page, name, value):
    select = page.locator(f'select[name="{name}"]')
    with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
        select.select_option(value)
    wait_rows(page)


def click_sort(page, column):
    button = page.locator(f'.sort-control[data-column="{column}"]')
    with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
        button.click()
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
            assert page.title() == "LS v2.28"
            assert request_count(page) == 75
            assert "75 tracks" in page.locator("#ls-filter-result-count").inner_text()

            # Text search through the real Finder UI.
            open_view(page)
            page.locator("#open-f4-search-btn").click()
            finder = page.locator("#finder-search-input")
            finder.fill("Alpha Search")
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                finder.press("Enter")
            wait_rows(page)
            assert current_param(page, "q") == "Alpha Search"
            assert row_ids(page) == ["canon-001"]
            assert_count_matches_rows(page, {"q": "Alpha Search"}) == 1

            # Category: track_user.manual_category overrides tracks.kind.
            open_view(page, {"q": "Manual Category"})
            click_multi_filter(page, "category_filter", "Instrumental")
            params = {"q": "Manual Category", "category_filter": "Instrumental"}
            assert current_param(page, "category_filter") == "Instrumental"
            assert row_ids(page) == ["canon-002"]
            assert page.locator("tr.track-row").first.get_attribute("data-main-category") == "Instrumental"
            assert_count_matches_rows(page, params) == 1

            # Broad Song / Instrumental category filters use the same canonical
            # category contract through the actual Category menu.
            open_view(page)
            click_multi_filter(page, "category_filter", "Song")
            params = {"category_filter": "Song"}
            assert current_param(page, "category_filter") == "Song"
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-main-category") == "Song"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 38

            open_view(page)
            click_multi_filter(page, "category_filter", "Instrumental")
            params = {"category_filter": "Instrumental"}
            assert current_param(page, "category_filter") == "Instrumental"
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-main-category") == "Instrumental"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 37

            # Type comes from tracks.source_task, not Category. Exercise the
            # actual Type dropdown so auto-submit/navigation is part of the proof.
            open_view(page)
            type_select = page.locator('select[name="kind_filter"]')
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                type_select.select_option("Cover")
            wait_rows(page)
            assert page.locator('select[name="kind_filter"]').input_value() == "Cover"
            assert page.evaluate(
                "() => new URL(window.location.href).searchParams.get('kind_filter')"
            ) == "Cover"
            rows = page.locator("tr.track-row")
            assert rows.count() > 0
            assert all(
                rows.nth(i).get_attribute("data-kind") == "Cover"
                for i in range(rows.count())
            )
            params = {"kind_filter": "Cover"}
            assert_count_matches_rows(page, params) == 25

            # Liked is canonical tracks.is_liked. Exercise the real Type
            # dropdown so auto-submit/navigation is part of the proof.
            open_view(page)
            type_select = page.locator('select[name="kind_filter"]')
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                type_select.select_option("__liked__")
            wait_rows(page)
            assert page.locator('select[name="kind_filter"]').input_value() == "__liked__"
            assert page.evaluate(
                "() => new URL(window.location.href).searchParams.get('kind_filter')"
            ) == "__liked__"
            assert page.locator(".like-toggle-btn.liked").count() == page.locator("tr.track-row").count()
            params = {"kind_filter": "__liked__"}
            assert_count_matches_rows(page, params) > 3

            # Flags through the actual Flags and Tags filter panel.
            open_view(page)
            page.locator("#ls-add-filter-button").click()
            page.locator("#user-tag-panel").wait_for(state="visible")
            page.locator('#user-flag-panel-stars .review-star[data-mask="1"]').click()
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                page.locator("#user-tag-filter-apply").click()
            wait_rows(page)
            params = {"flag_filter": "1"}
            assert current_param(page, "flag_filter") == "1"
            assert set(row_ids(page)) >= {"canon-001", "canon-002"}
            assert_count_matches_rows(page, params) == 2

            page.locator("#ls-add-filter-button").click()
            page.locator("#user-tag-panel").wait_for(state="visible")
            page.locator('#user-flag-panel-stars .review-star[data-mask="4"]').click()
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                page.locator("#user-tag-filter-apply").click()
            wait_rows(page)
            params = {"flag_filter": "1,4"}
            assert current_param(page, "flag_filter") == "1,4"
            assert row_ids(page) == ["canon-001"]
            assert_count_matches_rows(page, params) == 1

            # Exact tag through Finder structured-search UI. The fixture
            # track tags need not also exist in the user's global tag catalog.
            open_view(page)
            page.locator("#open-f4-search-btn").click()
            finder = page.locator("#finder-search-input")
            finder.fill("#rock")
            with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                finder.press("Enter")
            wait_rows(page)
            params = {"tag_filter": "#rock"}
            assert current_param(page, "tag_filter") == "#rock"
            assert set(row_ids(page)) == {"canon-001", "canon-002"}
            assert_count_matches_rows(page, params) == 2

            # Workspace through the real multi-select menu.
            open_view(page)
            click_multi_filter(page, "workspace", "Studio B")
            params = {"workspace": "Studio B"}
            assert current_param(page, "workspace") == "Studio B"
            assert all(
                page.locator("tr.track-row").nth(i).get_attribute("data-workspace") == "Studio B"
                for i in range(page.locator("tr.track-row").count())
            )
            assert_count_matches_rows(page, params) == 25

            # Local / Suno source split through the Audio dropdown.
            open_view(page)
            choose_auto_submit(page, "local_audio_filter", "with")
            params = {"local_audio_filter": "with"}
            assert current_param(page, "local_audio_filter") == "with"
            assert all(
                page.locator("tr.track-row .play-btn").nth(i).get_attribute("data-has-local-audio") == "true"
                for i in range(page.locator("tr.track-row .play-btn").count())
            )
            local_count = assert_count_matches_rows(page, params)
            assert local_count == 26

            open_view(page)
            choose_auto_submit(page, "local_audio_filter", "without")
            params = {"local_audio_filter": "without"}
            assert current_param(page, "local_audio_filter") == "without"
            assert all(
                page.locator("tr.track-row .play-btn").nth(i).get_attribute("data-has-local-audio") == "false"
                for i in range(page.locator("tr.track-row .play-btn").count())
            )
            assert_count_matches_rows(page, params) == 49

            # Sorts through the visible sort buttons; values remain server-side.
            open_view(page)
            click_sort(page, 2)
            assert current_param(page, "sort_by") == "title"
            assert current_param(page, "sort_dir") == "asc"
            assert row_ids(page)[0] == "canon-001"

            open_view(page)
            click_sort(page, 4)
            click_sort(page, 4)
            assert current_param(page, "sort_by") == "created"
            assert current_param(page, "sort_dir") == "desc"
            created_ids = row_ids(page)
            assert created_ids[0] != created_ids[-1]

            open_view(page)
            click_sort(page, 5)
            click_sort(page, 5)
            assert current_param(page, "sort_by") == "duration"
            assert current_param(page, "sort_dir") == "desc"
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
