import json
import sys
import traceback
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "browser-artifacts"
BASE_URL = "http://127.0.0.1:8765"


def write_diagnostics(page, console_messages, page_errors):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(ARTIFACTS / "select-audio-failure.png"), full_page=True)
    except Exception:
        pass
    details = {}
    try:
        details = page.evaluate(
            """() => {
              const selector = document.getElementById('audio-playlist-select');
              const summary = document.getElementById('audio-playlist-summary');
              const menu = document.getElementById('audio-playlist-menu');
              const chain = [];
              let node = menu;
              while (node && node.nodeType === 1) {
                const style = getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                chain.push({
                  tag: node.tagName,
                  id: node.id || '',
                  className: String(node.className || ''),
                  overflow: style.overflow,
                  overflowX: style.overflowX,
                  overflowY: style.overflowY,
                  position: style.position,
                  display: style.display,
                  visibility: style.visibility,
                  rect: {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height}
                });
                node = node.parentElement;
              }
              const inlineScripts = Array.from(document.querySelectorAll('script:not([src])')).map((script, index) => {
                const text = script.textContent || '';
                let syntaxError = '';
                try { new Function(text); } catch (error) { syntaxError = String(error); }
                return {
                  index,
                  length: text.length,
                  hasPlaylistActions: text.includes('LSPlaylistLibraryActionsInstalled'),
                  syntaxError,
                  start: text.slice(0, 180)
                };
              });
              return {
                selectorOpen: Boolean(selector?.open),
                selectorClass: selector?.className || '',
                summaryDisabled: summary?.getAttribute('aria-disabled') || '',
                menuText: menu?.innerText || '',
                menuHtml: menu?.innerHTML || '',
                playlistActionsInstalled: Boolean(window.LSPlaylistLibraryActionsInstalled),
                libraryApiKeys: Object.keys(window.LS?.library || {}),
                checkedValues: Array.from(document.querySelectorAll('#tracks-table .track-check:checked')).map(el => el.value),
                inlineScripts,
                chain
              };
            }"""
        )
    except Exception as exc:
        details = {"diagnostics_error": str(exc)}
    (ARTIFACTS / "browser-diagnostics.json").write_text(
        json.dumps(
            {
                "details": details,
                "console": console_messages,
                "page_errors": page_errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def assert_point_visible(locator, label):
    box = locator.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0, f"{label} has no visible box"
    point = locator.evaluate(
        """el => {
          const r = el.getBoundingClientRect();
          const x = r.left + Math.min(r.width / 2, Math.max(1, r.width - 2));
          const y = r.top + Math.min(r.height / 2, Math.max(1, r.height - 2));
          const hit = document.elementFromPoint(x, y);
          return {x, y, hitText: hit?.textContent || '', contained: Boolean(hit && (hit === el || el.contains(hit)))};
        }"""
    )
    assert point["contained"], f"{label} is clipped or covered: {point}"


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    console_messages = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1900, "height": 900})
        page.on(
            "console",
            lambda msg: console_messages.append(
                f"{msg.type}: {msg.text} @ {msg.location.get('url','')}:{msg.location.get('lineNumber','')}:{msg.location.get('columnNumber','')}"
            ),
        )
        page.on(
            "pageerror",
            lambda exc: page_errors.append(
                str(exc) + (" | " + str(getattr(exc, "stack", "")) if getattr(exc, "stack", "") else "")
            ),
        )

        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=30000)
            page.locator("tr.track-row").first.wait_for(state="visible", timeout=20000)

            assert page.title() == "LS v2.24"
            version_label = page.locator(".ls-sidebar-title-full")
            version_label.wait_for(state="visible", timeout=3000)
            assert version_label.inner_text().strip() == "LS v2.24"

            selector = page.locator("#audio-playlist-select")
            summary = page.locator("#audio-playlist-summary")
            assert selector.count() == 1
            assert summary.get_attribute("aria-disabled") == "true"

            page.locator(".ls-track-select-control").first.click()
            page.wait_for_function(
                "() => document.getElementById('audio-playlist-select')?.classList.contains('is-enabled')",
                timeout=5000,
            )
            assert summary.get_attribute("aria-disabled") == "false"

            summary.click()
            page.wait_for_function(
                "() => document.getElementById('audio-playlist-select')?.open === true",
                timeout=3000,
            )

            heading = page.locator("#audio-playlist-menu .library-playlist-menu-heading")
            heading.wait_for(state="attached", timeout=5000)
            assert heading.inner_text() == "Playlists (3)"
            assert_point_visible(heading, "Playlists heading")

            name_day = page.get_by_role("menuitem", name="Vārda diena (7)", exact=True)
            folk = page.get_by_role("menuitem", name="Tautas dziesmas (12)", exact=True)
            elizabete = page.get_by_role("menuitem", name="Elizabetei (10)", exact=True)
            for label, item in (
                ("Vārda diena (7)", name_day),
                ("Tautas dziesmas (12)", folk),
                ("Elizabetei (10)", elizabete),
            ):
                item.wait_for(state="attached", timeout=3000)
                assert_point_visible(item, label)

            page.once("dialog", lambda dialog: dialog.accept())
            name_day.click()

            page.wait_for_timeout(300)
            with urlopen(BASE_URL + "/playlists-json", timeout=5) as response:
                payload = json.load(response)
            target = next(item for item in payload["playlists"] if item["name"] == "Vārda diena")
            assert target["track_count"] == 8, target

            assert not page_errors, "Browser page errors: " + " | ".join(page_errors)
            (ARTIFACTS / "browser-console.txt").write_text(
                "\n".join(console_messages) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(ARTIFACTS / "select-audio-success.png"), full_page=True)
        except Exception:
            write_diagnostics(page, console_messages, page_errors)
            traceback.print_exc()
            browser.close()
            return 1

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
