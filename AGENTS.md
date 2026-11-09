# SKLAT Pro Engineering Rules

These rules apply to every future task in this project.

1. The UI language is Uzbek Latin. Code, comments, and commit messages are written in English.
2. Backend money values use `Decimal`. JSON APIs expose money as integer UZS. The UI formats money as `12 500 so'm`.
3. Every sale, payment, debt, and stock change runs inside a database transaction.
4. Self-verification is mandatory after every task:
   - Run migrations and `python manage.py check`.
   - Run all tests with `python manage.py test` and fix failures.
   - Maintain `tools/verify_ui.py` using Playwright and headless Chromium. It opens `/pos/workspace/` at 1280x720, 1024x768, and 390x844, logs in when needed, reports console errors, failed requests with status >= 400, product card count, and visible control overlap or text overflow, and saves screenshots in `tools/screens/`.
   - Look at the saved screenshots when image viewing is available.
   - Exercise new behavior through the real UI with Playwright or through the Django test client.
   - Finish every task with a `HISOBOT` section in Uzbek containing changes, files, checks with actual `OK`/`FAIL` results, known problems, and three manual test steps.
5. Never leave a feature half-done. Fix failures before reporting.
6. Keep the current Django templates and vanilla JavaScript stack. Do not add heavy build tooling or frameworks unless the project already uses them.

## Project Conventions

- Keep tenant boundaries enforced by `company` filters.
- Keep stock quantities authoritative in `inventory.StockLevel`.
- Preserve existing endpoint names and template naming when extending behavior.
- Prefer small, transaction-safe changes with focused tests.
