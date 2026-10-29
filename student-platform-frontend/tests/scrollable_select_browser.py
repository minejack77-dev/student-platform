"""Run with Playwright and Chrome installed; starts a local Vite test server."""
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

frontend = Path(__file__).resolve().parents[1]
url = "http://127.0.0.1:5189/tests/scrollable_select.html"
with tempfile.TemporaryFile() as log:
    server = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5189", "--strictPort"],
        cwd=frontend, stdout=log, stderr=log,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url, timeout=1).close()
                break
            except OSError:
                if server.poll() is not None:
                    raise RuntimeError("Vite failed to start")
                time.sleep(0.25)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1000, "height": 800})
            page.goto(url)
            trigger = page.get_by_role("button", name="Тест", exact=True)
            trigger.click()
            menu = page.get_by_role("listbox")
            expect(menu).to_be_visible()
            assert menu.evaluate("e => e.clientHeight") == 238  # 240px including borders
            assert menu.evaluate("e => e.scrollHeight > e.clientHeight")
            assert menu.evaluate("e => e.parentElement === document.body")
            assert menu.evaluate("""e => {
                const r = e.getBoundingClientRect();
                return e.contains(document.elementFromPoint(r.left + 20, r.top + 100));
            }"""), "Dropdown must paint above overlapping cards and escape overflow clipping"
            page.get_by_role("option", name="Задание 4", exact=True).click()
            expect(page.locator("#selected")).to_have_text("4")
            trigger.click()
            menu.press("End")
            assert menu.evaluate("e => e.scrollTop") > 0
            menu.press("Enter")
            expect(page.locator("#selected")).to_have_text("35")
            expect(menu).to_have_count(0)
            expect(trigger).to_be_focused()
            trigger.press("ArrowDown")
            menu.press("Home")
            menu.press("Enter")
            expect(page.locator("#selected")).to_have_text("2")
            page.evaluate("window.filled = true")
            trigger.click()
            menu.press("Home")
            menu.press("Enter")
            expect(page.locator("#selected")).to_have_text("1")
            trigger.click()
            menu.press("Escape")
            expect(trigger).to_be_focused()
            trigger.click()
            page.locator("#outside").click()
            expect(menu).to_have_count(0)
            page.evaluate("document.body.style.minHeight = '1800px'")
            trigger.click()
            page.evaluate("window.scrollTo(0, 15)")
            page.wait_for_function("""() => {
                const trigger = document.querySelector('[aria-haspopup="listbox"]');
                const menu = document.querySelector('[role="listbox"]');
                return Math.abs(menu.getBoundingClientRect().top - trigger.getBoundingClientRect().bottom - 4) < 1;
            }""")
            menu.press("Tab")
            expect(menu).to_have_count(0)
            expect(page.locator("#outside")).to_be_focused()
            browser.close()
            print("PASS: overlay stacking, clipping, scroll positioning, fixed height, selection, keyboard, refresh")
    finally:
        server.terminate()
        server.wait(timeout=10)
