"""Playwright test to verify product card redesign and dropdown actions."""

import os
import sys
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
        
        # 1. Desktop 1280x720
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(f"{BASE_URL}/products/", wait_until="networkidle")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/products/", wait_until="networkidle")
        page.wait_for_selector(".product-card", timeout=10000)
        
        card_count = page.locator(".product-card").count()
        print(f"Product cards found: {card_count}")
        assert card_count > 0, "No product cards found!"
        
        # Take desktop screenshot
        desktop_shot = SCREEN_DIR / "products-card-redesign-1280x720.png"
        page.screenshot(path=str(desktop_shot), full_page=False)
        print(f"Saved: {desktop_shot}")
        
        # Click Amallar button on the first card
        first_trigger = page.locator(".product-card .product-menu-trigger").first
        first_trigger.click()
        page.wait_for_timeout(300)
        
        # Verify dropdown is visible
        dropdown = page.locator(".product-card .product-dropdown").first
        is_visible = dropdown.is_visible()
        print(f"Dropdown visible after click: {is_visible}")
        assert is_visible, "Dropdown is not visible after clicking Amallar trigger!"
        
        # Check all 5 actions exist in dropdown
        items = dropdown.locator(".product-dropdown-item").all_text_contents()
        cleaned_items = [item.strip() for item in items]
        print(f"Dropdown items: {cleaned_items}")
        assert "Tahrirlash" in cleaned_items, "Tahrirlash missing from dropdown"
        assert "Nusxa ko'chirish" in cleaned_items, "Nusxa ko'chirish missing from dropdown"
        assert "Barcode" in cleaned_items, "Barcode missing from dropdown"
        assert "QR kod" in cleaned_items, "QR kod missing from dropdown"
        assert "O'chirish" in cleaned_items, "O'chirish missing from dropdown"
        
        # Take dropdown open screenshot
        dropdown_shot = SCREEN_DIR / "products-card-dropdown-open.png"
        page.screenshot(path=str(dropdown_shot), full_page=False)
        print(f"Saved: {dropdown_shot}")
        
        # Test closing dropdown via click outside
        page.locator("body").click(position={"x": 50, "y": 50})
        page.wait_for_timeout(200)
        assert not dropdown.is_visible(), "Dropdown did not close on outside click"
        print("Dropdown closes properly on outside click: OK")
        
        # Test Compact / Jadval view
        compact_btn = page.locator("[data-products-view='compact']")
        compact_btn.click()
        page.wait_for_timeout(300)
        compact_shot = SCREEN_DIR / "products-card-compact-view.png"
        page.screenshot(path=str(compact_shot), full_page=False)
        print(f"Saved: {compact_shot}")
        
        # Switch back to grid
        page.locator("[data-products-view='grid']").click()
        page.wait_for_timeout(200)
        
        page.close()
        context.close()
        
        # 2. Mobile 390x844
        context_mobile = browser.new_context(viewport={"width": 390, "height": 844})
        page_mobile = context_mobile.new_page()
        page_mobile.goto(f"{BASE_URL}/products/", wait_until="networkidle")
        login_if_needed(page_mobile)
        page_mobile.goto(f"{BASE_URL}/products/", wait_until="networkidle")
        page_mobile.wait_for_selector(".product-card", timeout=10000)
        
        mobile_shot = SCREEN_DIR / "products-card-mobile-390x844.png"
        page_mobile.screenshot(path=str(mobile_shot), full_page=False)
        print(f"Saved: {mobile_shot}")
        
        # Open dropdown on mobile
        page_mobile.locator(".product-card .product-menu-trigger").first.click()
        page_mobile.wait_for_timeout(300)
        mobile_dd_shot = SCREEN_DIR / "products-card-mobile-dropdown.png"
        page_mobile.screenshot(path=str(mobile_dd_shot), full_page=False)
        print(f"Saved: {mobile_dd_shot}")
        
        page_mobile.close()
        context_mobile.close()
        browser.close()
        print("ALL PLAYWRIGHT TESTS PASSED!")

if __name__ == "__main__":
    main()

