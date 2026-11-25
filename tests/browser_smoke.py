"""Run with: python3 tests/browser_smoke.py (requires Playwright Chromium)."""
import json
import os
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import handler
from playwright.sync_api import sync_playwright, expect


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            # Tests must never read/write the real shared Firebase project.
            page.route("https://**/*", lambda route: route.abort())
            page.add_init_script("localStorage.setItem('qp_settings', JSON.stringify({autoSound:false}));")
            url = f"http://127.0.0.1:{httpd.server_port}"
            page.goto(url)
            expect(page.locator(".set-card-modern")).to_have_count(20)

            page.locator(".btn-create-nav").click()
            expect(page.locator("#create-dropdown-menu")).to_be_visible()
            page.locator(".btn-quick-import-pill").click()
            expect(page.locator("#quick-import-modal")).to_be_visible()
            page.locator("#import-tab-paste").click()
            fixture = {
                "id": "browser_test", "title": 'Đề "test" của O\'Brien',
                "description": "Keep this description",
                "cards": [
                    {"id": "alpha", "term": "cat", "definition": "mèo", "image": "https://example.com/cat.png"},
                    {"id": 0, "term": "dog", "definition": "chó", "image": ""},
                    {"id": "gamma", "term": "bird", "definition": "chim", "image": ""},
                ],
            }
            page.locator("#quick-import-text").fill(json.dumps(fixture))
            page.locator("#import-pane-paste .btn-primary").click()
            expect(page.locator("#quick-import-modal")).to_be_hidden()
            expect(page.locator(".study-card")).to_be_visible()
            page.evaluate("toggleStar('alpha')")
            page.evaluate("cardsState[0].mastery = 2; saveProgressToStorage()")
            page.locator("#btn-edit-set").click()
            expect(page.locator("#create-desc")).to_have_value(fixture["description"])
            page.locator(".term-input").first.fill("kitten")
            page.locator("#btn-save-set-top").click()
            page.wait_for_function("currentSet?.cards[0].term === 'kitten' && document.getElementById('create-set-view').style.display === 'none'")
            assert page.evaluate("currentSet.cards[0].id") == "alpha"
            assert page.evaluate("currentSet.cards[0].image") == fixture["cards"][0]["image"]
            assert page.evaluate("cardsState[0].mastery") == 2
            assert page.evaluate("cardsState[0].starred")

            page.locator("#mode-flashcards").click()
            page.evaluate("toggleFlashcardShuffle()")
            selected = page.evaluate("getActiveFlashcardsPool()[fcIndex].id")
            before = page.evaluate("getActiveFlashcardsPool()[fcIndex].starred")
            page.locator("#fc-star-btn").click()
            assert page.evaluate("(id) => cardsState.find(c => c.id === id).starred", selected) != before
            page.evaluate("fcIsShuffled = false; window._shuffledPool = null; fcIndex = 1; renderFlashcardView(); saveActiveSession()")
            page.reload()
            expect(page.locator(".fc-counter")).to_have_text("Thẻ 2 / 3")

            page.locator("#mode-choice").click()
            page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice)); switchMode('flashcards')")
            # A cancelled answer transition must not replace the flashcard screen.
            page.wait_for_timeout(1000)
            expect(page.locator(".fc-container")).to_be_visible()
            expect(page.locator(".study-card")).to_have_count(0)

            page.locator("#mode-test").click()
            expect(page.locator(".test-q-card")).to_have_count(3)
            page.evaluate("submitTest()")
            expect(page.locator(".test-score-circle")).to_have_text("0%")
            page.evaluate("practiceMissedInLearn()")
            assert page.evaluate("currentRoundQueue.length") == 3
            page.locator("#mode-match").click()
            page.evaluate("initMatchGame()")
            page.evaluate("""() => {
                for (let i = 0; i < matchState.totalPairs; i++) {
                    onMatchTileClick('term_' + i);
                    onMatchTileClick('def_' + i);
                }
            }""")
            expect(page.locator(".match-win-card")).to_be_visible()

            page.evaluate("showDashboard()")
            page.locator("#dash-filter-input").fill("de test")
            # Match a simpler accentless substring without punctuation assumptions.
            page.locator("#dash-filter-input").fill("Brien")
            expect(page.locator(".set-card-modern")).to_have_count(1)
            page.locator(".set-card-modern .btn-icon-danger").click()
            # Dismiss confirms by default; title apostrophes must not break onclick.

            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#mob-nav-settings").click()
            expect(page.locator("#settings-modal")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#settings-modal")).to_be_hidden()
            assert not errors, errors
            browser.close()
            print("Browser smoke: import, edit/persistence, shuffle/star, resume, timers, test, match, search and mobile dialogs passed.")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


if __name__ == "__main__":
    main()
