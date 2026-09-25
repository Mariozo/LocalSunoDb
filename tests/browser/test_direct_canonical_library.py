import json
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "browser-artifacts" / "direct-canonical-library"
BASE_URL = "http://127.0.0.1:8765"


def row_ids(page):
    return page.locator("tr.track-row").evaluate_all(
        "rows => rows.map(row => row.dataset.trackId)"
    )


def open_view(page, params=None):
    query = "?" + urlencode(params or {}, doseq=True) if params else ""
    page.goto(BASE_URL + "/" + query, wait_until="domcontentloaded", timeout=30000)
    page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)


def assert_count(page, params, expected):
    response = page.request.get(
        BASE_URL + "/library-count?" + urlencode(params, doseq=True)
    )
    assert response.ok, response.status
    payload = response.json()
    assert payload["total"] == expected, (params, payload)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    console_messages = []
    page_errors = []
    timings = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        page = browser.new_page(viewport={"width": 1900, "height": 1000})
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            start = time.perf_counter()
            open_view(page)
            timings["initial_browser_ms"] = round((time.perf_counter() - start) * 1000, 2)
            assert "cutover-alpha" in row_ids(page)
            assert_count(page, {}, 75)

            start = time.perf_counter()
            open_view(page, {"q": "Gamma"})
            timings["search_browser_ms"] = round((time.perf_counter() - start) * 1000, 2)
            assert row_ids(page) == ["cutover-gamma"]
            assert_count(page, {"q": "Gamma"}, 1)

            open_view(page, {"category_filter": "Song"})
            assert "cutover-alpha" in row_ids(page)
            assert "cutover-beta" in row_ids(page)
            assert "cutover-gamma" not in row_ids(page)
            assert_count(page, {"category_filter": "Song"}, 50)

            start = time.perf_counter()
            open_view(page, {"kind_filter": "Cover"})
            timings["type_cover_browser_ms"] = round((time.perf_counter() - start) * 1000, 2)
            assert set(row_ids(page)) == {"cutover-alpha", "cutover-gamma"}
            assert_count(page, {"kind_filter": "Cover"}, 2)

            open_view(page, {"kind_filter": "__liked__"})
            assert "cutover-alpha" in row_ids(page)
            assert_count(page, {"kind_filter": "__liked__"}, 8)

            open_view(page, {"search_marks": "1", "flag_filter": "1"})
            assert {"cutover-alpha", "cutover-beta", "cutover-gamma"}.issubset(set(row_ids(page)))
            assert_count(page, {"search_marks": "1", "flag_filter": "1"}, 13)

            open_view(page, {"search_marks": "1", "flag_filter": "1,2"})
            assert row_ids(page) == ["cutover-beta"]
            assert_count(page, {"search_marks": "1", "flag_filter": "1,2"}, 1)

            open_view(page, {"tag_filter": "#rock"})
            assert row_ids(page) == ["cutover-gamma"]
            assert_count(page, {"tag_filter": "#rock"}, 1)

            start = time.perf_counter()
            open_view(page, {"workspace": "Studio A"})
            timings["workspace_browser_ms"] = round((time.perf_counter() - start) * 1000, 2)
            assert set(row_ids(page)) == {"cutover-alpha", "cutover-beta"}
            assert_count(page, {"workspace": "Studio A"}, 2)

            open_view(page, {"local_audio_filter": "with"})
            assert row_ids(page) == ["cutover-alpha"]
            assert_count(page, {"local_audio_filter": "with"}, 1)

            open_view(page, {"local_audio_filter": "without"})
            assert "cutover-alpha" not in row_ids(page)
            assert_count(page, {"local_audio_filter": "without"}, 74)

            open_view(page, {"sort_by": "title", "sort_dir": "asc"})
            assert row_ids(page)[:3] == ["cutover-alpha", "cutover-beta", "cutover-gamma"]

            open_view(page, {"sort_by": "created", "sort_dir": "desc"})
            assert row_ids(page)[:3] == ["cutover-alpha", "cutover-beta", "cutover-gamma"]

            open_view(page, {"sort_by": "duration", "sort_dir": "asc"})
            duration_ids = row_ids(page)
            assert duration_ids[0] == "cutover-004", duration_ids[:5]

            # Cursor/lazy loading in the actual Library page. The loader's
            # IntersectionObserver is rooted at .table-wrap, so scroll that real
            # container rather than the window. Wait until the initial fetch has
            # fully settled before exercising the observer-driven append.
            open_view(page, {"sort_by": "created", "sort_dir": "desc"})
            page.wait_for_function(
                "() => typeof window.LSLibraryLazyState === 'function' && !window.LSLibraryLazyState().loading",
                timeout=5000,
            )
            initial_loaded = page.locator("tr.track-row").count()
            assert 1 <= initial_loaded <= 40, initial_loaded
            lazy_state = page.evaluate("() => window.LSLibraryLazyState()")
            assert lazy_state["hasMore"] is True, lazy_state
            page.locator(".table-wrap").evaluate(
                "(el) => { el.scrollTop = el.scrollHeight; }"
            )
            page.wait_for_function(
                "(initial) => document.querySelectorAll('tr.track-row').length > initial",
                arg=initial_loaded,
                timeout=6000,
            )
            assert page.locator("tr.track-row").count() > initial_loaded

            # Follow the same browser JSON cursor contract until exhausted and
            # prove every canonical row is reachable exactly once.
            cursor = ""
            reached = []
            while True:
                params = {
                    "batch": "40",
                    "sort_by": "created",
                    "sort_dir": "desc",
                }
                if cursor:
                    params["cursor"] = cursor
                response = page.request.get(
                    BASE_URL + "/library-rows?" + urlencode(params, doseq=True)
                )
                assert response.ok, response.status
                payload = response.json()
                html = payload.get("html") or ""
                reached.extend(
                    page.evaluate(
                        """(html) => {
                          const template = document.createElement('template');
                          template.innerHTML = html;
                          return Array.from(template.content.querySelectorAll('tr.track-row'))
                            .map(row => row.dataset.trackId || '');
                        }""",
                        html,
                    )
                )
                if not payload.get("has_more"):
                    break
                cursor = payload.get("next_cursor") or ""
                assert cursor
            assert len(reached) == 75, len(reached)
            assert len(set(reached)) == 75

            # Local playback contract: the rendered Play control points at the
            # canonical media_files path, and the browser can fetch that audio.
            open_view(page, {"q": "Alpha Cover"})
            play = page.locator('tr[data-track-id="cutover-alpha"] .play-btn')
            play.wait_for(state="visible", timeout=5000)
            local_url = play.get_attribute("data-local-audio")
            assert local_url == "/local-audio?track_id=cutover-alpha", local_url
            audio_response = page.request.get(BASE_URL + local_url)
            assert audio_response.ok, audio_response.status
            assert "audio" in (audio_response.headers.get("content-type") or "").lower()

            assert not page_errors, page_errors
            (ARTIFACTS / "timings.json").write_text(
                json.dumps(timings, indent=2) + "\n",
                encoding="utf-8",
            )
            (ARTIFACTS / "console.txt").write_text(
                "\n".join(console_messages) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(ARTIFACTS / "success.png"), full_page=True)
        except Exception:
            try:
                page.screenshot(path=str(ARTIFACTS / "failure.png"), full_page=True)
            except Exception:
                pass
            (ARTIFACTS / "failure-console.txt").write_text(
                "\n".join(console_messages + page_errors) + "\n",
                encoding="utf-8",
            )
            traceback.print_exc()
            browser.close()
            return 1

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
