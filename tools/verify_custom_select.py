"""Playwright test to verify custom floating select dropdown and theme switching."""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("SKLAT_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("SKLAT_DEMO_EMAIL", "demo@sklat.local")
PASSWORD = os.environ.get("SKLAT_DEMO_PASSWORD", "demo12345")
SCREEN_DIR = Path(__file__).resolve().parent / "screens"
SCREEN_DIR.mkdir(parents=True, exist_ok=True)

def login_if_needed(page):
    if "/login" not in page.url:
        return
    page.locator('input[name="username"]').fill(EMAIL)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(f"{BASE_URL}/products/", wait_until="networkidle")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/products/", wait_until="networkidle")

        # 1. Check custom select wrappers exist
        page.wait_for_selector(".custom-select-wrapper", timeout=10000)
        wrappers_count = page.locator(".custom-select-wrapper").count()
        print(f"Custom select wrappers initialized: {wrappers_count}")
        assert wrappers_count >= 5, f"Expected at least 5 custom selects, found {wrappers_count}"

        # 2. Click the status select trigger (4th trigger or status wrapper)
        status_wrapper = page.locator(".custom-select-wrapper.status")
        status_trigger = status_wrapper.locator(".custom-select-trigger")
        status_trigger.click()
        page.wait_for_timeout(300)

        # Check menu is open
        is_open = status_wrapper.evaluate("el => el.classList.contains('is-open')")
        print(f"Status dropdown is open: {is_open}")
        assert is_open, "Custom select did not open on trigger click"

        # Check options
        options = status_wrapper.locator(".custom-select-option").all_text_contents()
        options = [o.strip() for o in options]
        print(f"Status options: {options}")
        assert "Barcha holatlar" in options
        assert "Faol" in options
        assert "Nofaol" in options

        # Dark theme screenshot of custom select
        dark_shot = SCREEN_DIR / "custom-select-dark-theme.png"
        page.screenshot(path=str(dark_shot), full_page=False)
        print(f"Saved: {dark_shot}")

        # 3. Toggle theme to Light mode
        page.locator("#themeToggleBtn").click()
        page.wait_for_timeout(400)
        
        # Verify theme is light
        theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        print(f"Current theme: {theme}")
        assert theme == "light", f"Expected theme light, got {theme}"

        # Open the status dropdown in light mode
        status_wrapper.locator(".custom-select-trigger").click()
        page.wait_for_timeout(300)

        # Light theme screenshot
        light_shot = SCREEN_DIR / "custom-select-light-theme.png"
        page.screenshot(path=str(light_shot), full_page=False)
        print(f"Saved: {light_shot}")

        # 4. Click 'Faol' option
        faol_opt = status_wrapper.locator('.custom-select-option[data-value="active"]')
        faol_opt.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)

        print(f"URL after filter selection: {page.url}")
        assert "status=active" in page.url, f"Expected status=active in URL, got {page.url}"

        # Filtered screenshot
        filtered_shot = SCREEN_DIR / "products-filtered-active.png"
        page.screenshot(path=str(filtered_shot), full_page=False)
        print(f"Saved: {filtered_shot}")

        print(f"Console errors: {console_errors}")
        page.close()
        context.close()
        browser.close()
        print("CUSTOM SELECT VERIFICATION COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
