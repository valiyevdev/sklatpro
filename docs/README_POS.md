# SKLAT PRO POS

## Run

From the project root:

```powershell
python manage.py migrate
python manage.py runserver
```

Open `/pos/workspace/`. The workspace uses the selected POS terminal and its warehouse. An open cash shift is required before checkout.

Run the required verification:

```powershell
python manage.py check
python manage.py test
python tools/verify_ui.py
```

`tools/verify_ui.py` checks 1280x720, 1024x768, and 390x844 with headless Chromium and saves screenshots under `tools/screens/`.

## Seed Data

Use the project seed/demo process when available, or create these records through Django admin or the existing management pages:

1. Company and active user.
2. Warehouse and active POS terminal.
3. Product with a `StockLevel`, selling price, minimum stock, and optional wholesale price.
4. Open shift with starting cash.
5. Optional customers, credit limits, and expense categories.

## Roles

- `COMPANY_ADMIN` / Egasi: sees profit and purchase prices, manages products/stock, changes prices, cancels sales, and processes returns.
- `STAFF` / Kassir: sells, manages customers, views permitted sales, and takes payments. Purchase prices/profit, stock mutations, price overrides, deletions, cancellations, and returns are blocked server-side.
- `MANAGER`: retains existing management capabilities where the application allows them.

## Shortcuts

- `/`: focus product search
- `F2`: customer selector
- `F4`: credit sale
- `F8`: payment modal
- `F9`: hold cart
- `Esc`: close active modal

The `Yordam` button opens the in-app shortcut sheet. The light/dark theme choice, sound feedback, vibration feedback, cart snapshot, and product catalog cache are stored in browser localStorage.

## Offline Hook

The POS displays `Oflayn` when the browser loses connectivity and keeps a persistent product cache for catalog browsing. Sales are intentionally not replayed automatically: checkout is server-authoritative and requires a valid authenticated session, shift, stock lock, and idempotency key. This avoids duplicate or unverified offline sales. A future sync queue should send complete signed sale payloads to `create_sale` after reconnecting.

## Operational Notes

- Money is stored as `Decimal` and API/UI amounts are UZS.
- Stock authority is `inventory.StockLevel`.
- Returns, refunds, debt reduction, stock restoration, and audit entries run transactionally.
- Activity logs record price changes, product deletions, receipt cancellation, returns, and shift closing.
- `Ombor` links to the warehouse overview; purchase receiving remains the canonical full Kirim workflow.
- Product cards provide a fast `Qoldiq qo'shish` path for owner/manager users and create canonical `StockMovement` records.
- Use the inventory movement history and purchase receiving pages for supplier, revision, and movement reconciliation.
