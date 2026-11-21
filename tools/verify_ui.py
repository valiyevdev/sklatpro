"""Strict Playwright verification for the Uzbek POS workspace."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


BASE_URL = os.environ.get("SKLAT_BASE_URL", "http://127.0.0.1:8000")
POS_PATH = os.environ.get("SKLAT_POS_PATH", "/pos/workspace/")
INVENTORY_PATH = os.environ.get("SKLAT_INVENTORY_PATH", "/inventory/table/")
EMAIL = os.environ.get("SKLAT_DEMO_EMAIL", "demo@sklat.local")
PASSWORD = os.environ.get("SKLAT_DEMO_PASSWORD", "demo12345")
TERMINAL_ID = os.environ.get("SKLAT_TERMINAL_ID", "")
SCREEN_DIR = Path(__file__).resolve().parent / "screens"
VIEWPORTS = ((1024, 768), (1280, 720), (1440, 900), (1536, 864), (1920, 1080), (390, 844))
INVENTORY_VIEWPORTS = ((1280, 720), (1536, 864), (1920, 1080), (390, 844))


def login_if_needed(page: Page) -> None:
    if "/login" not in page.url:
        return
    page.locator('input[name="username"]').fill(EMAIL)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle")


STRICT_AUDIT = r"""() => {
    const visible = (node) => {
        const style = getComputedStyle(node);
        const box = node.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
    };
    const label = (node) => node.getAttribute('aria-label') || node.innerText?.trim().slice(0, 80) || node.tagName.toLowerCase();
    const activeModal = document.querySelector('.pos-modal-overlay.active');
    const interactive = [...document.querySelectorAll('button,a,input,select,[role="button"],.pos-pill,.pos-category-pill,.pos-stock-badge')].filter(node => visible(node) && (!activeModal || activeModal.contains(node)));
    const failures = [];
    if (document.documentElement.scrollWidth > innerWidth + 1) failures.push({type:'page-horizontal-overflow', selector:'html', numbers:`scrollWidth=${document.documentElement.scrollWidth}, width=${innerWidth}`});
    for (const node of interactive) {
        const box = node.getBoundingClientRect();
        if (box.left < -1 || box.right > innerWidth + 1) failures.push({type:'viewport-boundary', selector:label(node), numbers:`left=${box.left.toFixed(1)}, right=${box.right.toFixed(1)}, width=${innerWidth}`});
    }
    const isParent = (a, b) => a.contains(b) || b.contains(a);
    for (let i = 0; i < interactive.length; i++) for (let j = i + 1; j < interactive.length; j++) {
        const a = interactive[i], b = interactive[j];
        if (isParent(a, b)) continue;
        const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
        const w = Math.min(ar.right, br.right) - Math.max(ar.left, br.left);
        const h = Math.min(ar.bottom, br.bottom) - Math.max(ar.top, br.top);
        if (w > 2 && h > 2) failures.push({type:'interactive-intersection', selector:`${label(a)} <> ${label(b)}`, numbers:`intersection=${w.toFixed(1)}x${h.toFixed(1)}`});
    }
    const textNodes = [...document.querySelectorAll('button,a,[role="button"],label,span,strong,p,h1,h2,h3')].filter(visible);
    for (const node of textNodes) {
        if (node.closest('[data-allow-truncate]')) continue;
        if (node.scrollWidth > node.clientWidth + 1) failures.push({type:'text-clipping', selector:label(node), numbers:`scrollWidth=${node.scrollWidth}, clientWidth=${node.clientWidth}`});
        const style = getComputedStyle(node), line = parseFloat(style.lineHeight) || 16, padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
        if (node.matches('.pos-pill,.pos-stock-badge,.pos-category-pill,.pos-product-meta span') && node.scrollHeight - padding > line * 1.8) failures.push({type:'chip-wrap', selector:label(node), numbers:`contentHeight=${node.scrollHeight - padding}, lineHeight=${line}`});
        if (/\bUZS\b|\d,\d{3}(?:,\d{3})*/.test(node.innerText || '')) failures.push({type:'money-format', selector:label(node), numbers:node.innerText.trim().slice(0, 100)});
    }
    for (const node of interactive.filter(n => n.closest('.pos-topbar') && n.matches('button,a,.pos-pill,.pos-back-btn'))) {
        if (node.closest('[data-allow-wrap]')) continue;
        const style = getComputedStyle(node), box = node.getBoundingClientRect();
        const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.2;
        const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
        if (node.scrollHeight - padding > lineHeight * 1.6 + 2) failures.push({type:'header-button-wrap', selector:label(node), numbers:`contentHeight=${node.scrollHeight - padding}, lineHeight=${lineHeight.toFixed(1)}`});
    }
    const allowedScroll = '#product-grid,#cart-items,#pos-catalog-area';
    for (const node of [...document.querySelectorAll('*')].filter(visible)) {
        if (node.matches(allowedScroll) || node.closest(allowedScroll)) continue;
        const style = getComputedStyle(node);
        if ((style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowX === 'auto' || style.overflowX === 'scroll') && (node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1)) failures.push({type:'unexpected-scrollbar', selector:label(node), numbers:`scroll=${node.scrollWidth}x${node.scrollHeight}, client=${node.clientWidth}x${node.clientHeight}`});
    }
    for (const select of document.querySelectorAll('select')) if (visible(select) && select.scrollWidth > select.clientWidth + 1) failures.push({type:'select-clipping', selector:label(select), numbers:`scrollWidth=${select.scrollWidth}, clientWidth=${select.clientWidth}`});
    return failures;
}"""


INVENTORY_AUDIT = """() => {
    const root = document.querySelector('#main-content') || document;
    const visible = (node) => {
        const style = getComputedStyle(node);
        const box = node.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
    };
    const label = (node) => node.getAttribute('aria-label') || node.innerText?.trim().slice(0, 60) || node.tagName.toLowerCase();
    const failures = [];
    const add = (type, selector, numbers) => failures.push({type, selector, numbers});
    if (document.documentElement.scrollWidth > innerWidth + 1) add('page-horizontal-overflow', 'html', `scrollWidth=${document.documentElement.scrollWidth}, width=${innerWidth}`);
    const interactive = [...root.querySelectorAll('a,button,input,select')].filter(visible);
    for (const node of interactive) {
        const box = node.getBoundingClientRect();
        if (box.left < -1 || box.right > innerWidth + 1) add('viewport-boundary', label(node), `left=${box.left.toFixed(1)}, right=${box.right.toFixed(1)}, width=${innerWidth}`);
    }
    const isParent = (a, b) => a.contains(b) || b.contains(a);
    for (let i = 0; i < interactive.length; i++) for (let j = i + 1; j < interactive.length; j++) {
        const a = interactive[i], b = interactive[j];
        if (isParent(a, b)) continue;
        const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
        const w = Math.min(ar.right, br.right) - Math.max(ar.left, br.left);
        const h = Math.min(ar.bottom, br.bottom) - Math.max(ar.top, br.top);
        if (w > 2 && h > 2) add('interactive-intersection', `${label(a)} <> ${label(b)}`, `intersection=${w.toFixed(1)}x${h.toFixed(1)}`);
    }
    const text = [...root.querySelectorAll('.page-title,.invt-count,.invt-count *,.invt-price,.invt-status,.invt-label,.invt-stat__value,.invt-btn,.fp-label,.fp-btn,.fp-toggle,.fp-result,.fp-chip,.custom-select-label,.custom-select-option-label')].filter(visible);
    for (const node of text) {
        if (node.closest('[data-allow-truncate]')) continue;
        if (node.scrollWidth > node.clientWidth + 1) add('text-clipping', label(node), `scrollWidth=${node.scrollWidth}, clientWidth=${node.clientWidth}`);
    }
    for (const node of [...root.querySelectorAll('.fp-btn,.fp-toggle')].filter(visible)) {
        if (node.scrollHeight > node.clientHeight + 2) add('button-wrap', label(node), `scrollHeight=${node.scrollHeight}, clientHeight=${node.clientHeight}`);
    }
    for (const node of [...root.querySelectorAll('.fp-select__control,.fp-search__input')].filter(visible)) {
        if (node.scrollWidth > node.clientWidth + 1) add('field-clipping', label(node), `scrollWidth=${node.scrollWidth}, clientWidth=${node.clientWidth}`);
    }
    const card = root.querySelector('.invt-table-card');
    const table = root.querySelector('.invt-table-card .table-pro');
    const tableVisible = card && visible(card);
    if (tableVisible && table) {
        if (table.scrollWidth > table.clientWidth + 1) add('table-overflow', '.table-pro', `scrollWidth=${table.scrollWidth}, clientWidth=${table.clientWidth}`);
        for (const node of [...table.querySelectorAll('thead th')].filter(visible)) if (node.scrollWidth > node.clientWidth + 1) add('header-clipping', label(node), `scrollWidth=${node.scrollWidth}, clientWidth=${node.clientWidth}`);
        const numHead = table.querySelector('thead th.invt-col--num');
        if (numHead && getComputedStyle(numHead).textAlign !== 'right') add('numeric-align', 'thead numeric', getComputedStyle(numHead).textAlign);
        const numCell = table.querySelector('tbody td.invt-col--num');
        if (numCell && getComputedStyle(numCell).textAlign !== 'right') add('numeric-align', 'tbody numeric', getComputedStyle(numCell).textAlign);
        if (!table.querySelector('tbody .table-pro__row')) add('empty-table', '.table-pro', 'no rows');
    }
    const cards = [...root.querySelectorAll('.invt-card')].filter(visible).length;
    if (!tableVisible && cards === 0) add('empty-cards', '.invt-cards', 'no cards');
    for (const node of [...root.querySelectorAll('.invt-price')].filter(visible)) {
        if (!/^\\d{1,3}( \\d{3})* so'm$/.test(node.innerText.trim())) add('money-format', label(node), node.innerText.trim());
    }
    return {failures, tableVisible, cards, rows: tableVisible ? table.querySelectorAll('.table-pro__row').length : 0};
}"""


def verify_inventory_viewport(page: Page, width: int, height: int) -> dict:
    console_errors: list[str] = []
    failed_requests: list[str] = []
    interaction_failures: list[dict] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(f"pageerror: {error}"))
    page.on("response", lambda response: failed_requests.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    url = f"{BASE_URL}{INVENTORY_PATH}"
    page.goto(url, wait_until="domcontentloaded")
    login_if_needed(page)
    page.goto(url, wait_until="domcontentloaded")
    page.locator(".invt-header").wait_for(state="visible", timeout=15000)
    page.locator(".fp-panel").wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(400)

    def add_failure(kind: str, selector: str, numbers: str) -> None:
        interaction_failures.append({"type": kind, "selector": selector, "numbers": numbers})

    try:
        if not page.locator("[data-fp-controls]").is_visible():
            page.locator("[data-fp-toggle]").click()
            page.wait_for_timeout(200)

        page.keyboard.press("Control+K")
        if not page.evaluate("() => document.activeElement && document.activeElement.matches('[data-fp-search]')"):
            add_failure("shortcut-not-focusing", "Ctrl+K", "search input not focused")

        # ---------- Custom dropdowns replace the native selects ----------
        for field_id, trigger_id in (
            ("fp-status-filter", "fp-status-trigger"),
            ("fp-category-filter", "fp-category-trigger"),
            ("fp-brand-filter", "fp-brand-trigger"),
        ):
            if not page.locator(f"#{trigger_id}").is_visible():
                add_failure("custom-select-trigger", f"#{trigger_id}", "trigger not visible")
            if page.locator(f"#{field_id}").get_attribute("aria-hidden") != "true":
                add_failure("custom-select-native", f"#{field_id}", "native select still exposed")

        page.locator("#fp-status-trigger").click()
        status_menu = page.locator("#fp-status-menu")
        if not status_menu.is_visible():
            add_failure("custom-select-open", "#fp-status-trigger", "menu not visible")
        if status_menu.locator(".custom-select-option").count() != page.locator("#fp-status-filter option").count():
            add_failure("custom-select-options", "#fp-status-menu", "menu options differ from native select")
        status_option = status_menu.locator('.custom-select-option[data-value="low_stock"]')
        if not status_option.count():
            add_failure("custom-select-option", "#fp-status-menu", "low_stock option missing")
        else:
            status_option.click()
            page.wait_for_timeout(150)
            native_status = page.locator("#fp-status-filter").input_value()
            if native_status != "low_stock":
                add_failure("custom-select-native-value", "#fp-status-filter", native_status)
            status_label = page.locator("#fp-status-value").inner_text().strip()
            if status_label != "Kam qolgan":
                add_failure("custom-select-label", "#fp-status-value", status_label)
        if status_menu.is_visible():
            add_failure("custom-select-close", "#fp-status-menu", "menu stayed open after choosing an option")

        with page.expect_navigation(wait_until="domcontentloaded"):
            page.locator(".fp-btn--primary").click()
        page.wait_for_timeout(350)
        if "status=low_stock" not in page.url:
            add_failure("apply-status", "Qo'llash", page.url)
        page.locator(".fp-panel.fp-custom-ready").wait_for(state="visible", timeout=15000)
        status_label = page.locator("#fp-status-value").inner_text().strip()
        if status_label != "Kam qolgan":
            add_failure("status-persist", "#fp-status-value", status_label)

        # Keyboard: ArrowDown opens the menu, Escape restores focus.
        page.locator("#fp-status-trigger").focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        if not page.locator("#fp-status-menu").is_visible():
            add_failure("keyboard-open", "#fp-status-trigger", "ArrowDown did not open the menu")
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        if page.locator("#fp-status-menu").is_visible():
            add_failure("keyboard-close", "#fp-status-menu", "Escape did not close the menu")
        if not page.evaluate("() => document.activeElement && document.activeElement.id === 'fp-status-trigger'"):
            add_failure("keyboard-focus", "#fp-status-trigger", "focus not restored after Escape")

        with page.expect_navigation(wait_until="domcontentloaded"):
            page.locator(".fp-btn--outline").click()
        page.wait_for_timeout(350)
        if any(part in page.url for part in ("q=", "status=", "category=", "brand=")):
            add_failure("clear-all", "Tozalash", page.url)

        # ---------- Category dropdown applies and persists ----------
        page.locator(".fp-panel.fp-custom-ready").wait_for(state="visible", timeout=15000)
        page.locator("#fp-category-trigger").click()
        category_options = page.locator("#fp-category-menu .custom-select-option")
        if category_options.count() > 1:
            category_option = category_options.nth(1)
            category_value = category_option.get_attribute("data-value")
            category_label = category_option.inner_text().strip()
            category_option.click()
            page.wait_for_timeout(150)
            native_category = page.locator("#fp-category-filter").input_value()
            if native_category != category_value:
                add_failure("custom-select-native-value", "#fp-category-filter", native_category)
            selected_label = page.locator("#fp-category-value").inner_text().strip()
            if selected_label != category_label:
                add_failure("custom-select-label", "#fp-category-value", selected_label)
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.locator(".fp-btn--primary").click()
            page.wait_for_timeout(350)
            if f"category={category_value}" not in page.url:
                add_failure("apply-category", "Kategoriya", page.url)
            page.locator(".fp-panel.fp-custom-ready").wait_for(state="visible", timeout=15000)
            selected_label = page.locator("#fp-category-value").inner_text().strip()
            if selected_label != category_label:
                add_failure("category-persist", "#fp-category-value", selected_label)
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.locator(".fp-btn--outline").click()
            page.wait_for_timeout(300)

        product_name = page.locator(".table-pro__cell-main, .invt-card__name").first.inner_text().strip()
        search_term = product_name.split()[0] if product_name else "a"
        page.fill("[data-fp-search]", search_term)
        try:
            page.wait_for_url(lambda current: "q=" in current, wait_until="domcontentloaded", timeout=5000)
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        if "q=" not in page.url:
            add_failure("search-debounce", "[data-fp-search]", page.url)
        # Clean up by URL: clicking the link while the debounced navigation is
        # still settling can race on slow mobile viewports.
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        page.locator("[data-fp-toggle]").click()
        if page.locator("[data-fp-controls]").is_visible():
            add_failure("toggle-close", ".fp-toggle", "controls still visible")
        stored = page.evaluate("() => localStorage.getItem('sklat-filter-panel-open')")
        if stored != "0":
            add_failure("toggle-state", ".fp-toggle", f"localStorage={stored}")
        page.reload(wait_until="domcontentloaded")
        page.locator(".fp-panel").wait_for(state="visible", timeout=15000)
        if page.locator("[data-fp-controls]").is_visible():
            add_failure("toggle-persist", ".fp-panel", "panel did not stay collapsed")
        page.locator("[data-fp-toggle]").click()
        page.wait_for_timeout(200)
        if not page.locator("[data-fp-controls]").is_visible():
            add_failure("toggle-open", ".fp-toggle", "controls not visible")

        # ---------- Progressive enhancement: the form works without JS ----------
        if width == INVENTORY_VIEWPORTS[0][0]:
            nojs_context = page.context.browser.new_context(
                viewport={"width": width, "height": height},
                java_script_enabled=False,
                storage_state=page.context.storage_state(),
            )
            try:
                nojs_page = nojs_context.new_page()
                nojs_page.goto(url, wait_until="domcontentloaded")
                nojs_page.locator(".fp-panel").wait_for(state="visible", timeout=15000)
                if not nojs_page.locator("#fp-category-filter").is_visible():
                    add_failure("nojs-native-select", "#fp-category-filter", "native select hidden without JS")
                if nojs_page.locator("#fp-category-trigger").is_visible():
                    add_failure("nojs-trigger", "#fp-category-trigger", "custom trigger visible without JS")
                nojs_category_count = nojs_page.locator("#fp-category-filter option").count()
                if nojs_category_count > 1:
                    nojs_value = nojs_page.locator("#fp-category-filter option").nth(1).get_attribute("value")
                    nojs_page.select_option("#fp-category-filter", nojs_value)
                    with nojs_page.expect_navigation(wait_until="domcontentloaded"):
                        nojs_page.locator(".fp-btn--primary").click()
                    if f"category={nojs_value}" not in nojs_page.url:
                        add_failure("nojs-apply-category", "no-JS", nojs_page.url)
            finally:
                nojs_context.close()
    except Exception as exc:
        add_failure("interaction-exception", "filter panel", str(exc))

    failures = page.evaluate(INVENTORY_AUDIT)
    failures["failures"].extend(interaction_failures)
    shot = SCREEN_DIR / f"inventory-{width}x{height}.png"
    page.screenshot(path=str(shot), full_page=True)
    menu_shot = SCREEN_DIR / f"inventory-custom-select-{width}x{height}.png"
    try:
        page.locator("#fp-category-trigger").click()
        page.wait_for_timeout(250)
        page.screenshot(path=str(menu_shot), full_page=False)
    except Exception as exc:
        failures["failures"].append({"type": "menu-screenshot", "selector": "#fp-category-trigger", "numbers": str(exc)})
    return {
        "viewport": f"{width}x{height}",
        "table_visible": failures.get("tableVisible"),
        "rows": failures.get("rows"),
        "cards": failures.get("cards"),
        "failures": failures["failures"],
        "console_errors": console_errors,
        "failed_requests": failed_requests,
        "screenshot": str(shot),
        "custom_select_screenshot": str(menu_shot),
    }


def verify_viewport(page: Page, width: int, height: int, exercise: bool) -> dict:
    console_errors: list[str] = []
    failed_requests: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(f"pageerror: {error}"))
    page.on("response", lambda response: failed_requests.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    url = f"{BASE_URL}{POS_PATH}"
    if TERMINAL_ID:
        url += f"?terminal={TERMINAL_ID}"
    page.goto(url, wait_until="domcontentloaded")
    login_if_needed(page)
    page.goto(url, wait_until="domcontentloaded")
    page.locator("#product-grid:visible, #catalog-empty:visible, #catalog-skeleton:visible").first.wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(800)
    all_failures = []
    screenshots = []
    def audit_state(name):
        failures = page.evaluate(STRICT_AUDIT)
        for failure in failures: failure['state'] = name
        all_failures.extend(failures)
        shot = SCREEN_DIR / f"pos-{width}x{height}-{name}.png"
        page.screenshot(path=str(shot), full_page=True)
        screenshots.append(str(shot))
    cards = page.locator(".pos-product-card").count()
    audit_state('grid-empty')
    page.locator(".pos-view-toggle[data-view='list']").click()
    page.wait_for_timeout(300)
    audit_state('list-empty')
    page.locator(".pos-view-toggle[data-view='grid']").click()
    for card in page.locator('.pos-product-card:not(.is-disabled)').all()[:3]: card.click()
    page.wait_for_timeout(500)
    audit_state('grid-cart3')
    page.locator(".pos-view-toggle[data-view='list']").click()
    page.wait_for_timeout(300)
    audit_state('list-cart3')
    page.locator(".pos-view-toggle[data-view='grid']").click()
    modal_actions = [
        ('payment', "#payment-modal", "button:has-text(\"To'lash\")"),
        ('credit', '#credit-modal', "button:has-text('Nasiyaga berish')"),
        ('customer', '#customer-modal', "button:has-text('Mijoz')"),
        ('more', '#header-menu-modal', '.pos-more-btn'),
        ('low-stock', '#low-stock-modal', "button:has-text('Kam qoldi')"),
    ]
    for name, modal, trigger in modal_actions:
        try:
            page.locator(trigger).first.click()
            page.wait_for_timeout(250)
            if not page.locator(f'{modal}.active').count(): all_failures.append({'state':name,'type':'modal-not-open','selector':modal,'numbers':'not active'})
            audit_state(name)
            page.locator(f'{modal} .pos-modal-close').first.click()
        except Exception as exc:
            all_failures.append({'state':name,'type':'modal-exception','selector':modal,'numbers':str(exc)})
    return {'viewport': f'{width}x{height}', 'product_cards': cards, 'console_errors': console_errors, 'failed_requests': failed_requests, 'failures': all_failures, 'exercise_error': '', 'screenshot': ', '.join(screenshots)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict Playwright UI verification")
    parser.add_argument("--inventory-only", action="store_true", help="Skip the POS workspace checks")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    inventory_results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        if not args.inventory_only:
            for index, (width, height) in enumerate(VIEWPORTS):
                context = browser.new_context(viewport={'width': width, 'height': height})
                page = context.new_page()
                try:
                    results.append(verify_viewport(page, width, height, exercise=index == 0))
                except Exception as exc:
                    results.append({'viewport': f'{width}x{height}', 'product_cards': 0, 'console_errors': [str(exc)], 'failed_requests': [], 'failures': [{'type':'verifier-exception', 'selector':'page', 'numbers':str(exc)}], 'exercise_error':'', 'screenshot':''})
                page.close()
                context.close()
        for width, height in INVENTORY_VIEWPORTS:
            context = browser.new_context(viewport={'width': width, 'height': height})
            page = context.new_page()
            try:
                inventory_results.append(verify_inventory_viewport(page, width, height))
            except Exception as exc:
                inventory_results.append({'viewport': f'{width}x{height}', 'table_visible': False, 'rows': 0, 'cards': 0, 'console_errors': [str(exc)], 'failed_requests': [], 'failures': [{'type':'verifier-exception', 'selector':'page', 'numbers':str(exc)}], 'screenshot':''})
            page.close()
            context.close()
        browser.close()
    failed = False
    for result in results:
        print(f"\n[{result['viewport']}] cards={result['product_cards']} screenshot={result['screenshot']}")
        for failure in result['failures']:
            print(f"FAIL | {result['viewport']} | {failure['type']} | {failure['selector']} | {failure['numbers']}")
        for error in result['console_errors']:
            print(f"FAIL | {result['viewport']} | console | page | {error}")
        for response in result['failed_requests']:
            print(f"FAIL | {result['viewport']} | http | page | {response}")
        if result['exercise_error']:
            print(f"FAIL | {result['viewport']} | exercise | page | {result['exercise_error']}")
        failed |= bool(result['failures'] or result['console_errors'] or result['failed_requests'] or result['exercise_error'])
    for result in inventory_results:
        print(f"\n[inventory {result['viewport']}] table={result['table_visible']} rows={result['rows']} cards={result['cards']} screenshot={result['screenshot']} custom_select={result.get('custom_select_screenshot', '')}")
        for failure in result['failures']:
            print(f"FAIL | inventory {result['viewport']} | {failure['type']} | {failure['selector']} | {failure['numbers']}")
        for error in result['console_errors']:
            print(f"FAIL | inventory {result['viewport']} | console | page | {error}")
        for response in result['failed_requests']:
            print(f"FAIL | inventory {result['viewport']} | http | page | {response}")
        failed |= bool(result['failures'] or result['console_errors'] or result['failed_requests'])
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
