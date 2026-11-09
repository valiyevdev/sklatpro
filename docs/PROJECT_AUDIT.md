# PROJECT AUDIT — Existing SKLAT Warehouse System

## Overview

This is an existing Django-based warehouse management system that was previously developed into a multi-tenant SaaS application. It uses SQLite, Django templates with Bootstrap 5, and has been partially modernized with company isolation, roles, and activity logging.

**Database**: SQLite (PostgreSQL config prepared but not active)
**Backend**: Django 4.2+ with Python 3.13
**Frontend**: Django Templates + Bootstrap 5.3 + Chart.js + Bootstrap Icons
**Auth**: Custom User model (email-based), django-axes brute-force protection
**Multi-tenant**: Yes — ForeignKey-based company isolation on all models

---

## Existing Apps

| App | Purpose | Status |
|-----|---------|--------|
| `warehouse_system` | Main project config, login/logout views | Working |
| `products` | Product CRUD, barcode/QR generation | Working |
| `inventory` | Dashboard, stock IN/OUT transactions | Working (has bugs) |
| `finance` | Customer/supplier debts, payments | Working (has bugs) |
| `activity` | Activity timeline logging | Partially working (company bug) |
| `users` | Company registration, user management, employees | Working |

---

## Database Models

### Company (users.models.Company)
- UUID primary key
- company_name, slug (auto-generated), logo, phone, email, address, city, country, tax_number
- subscription_plan (free/basic/professional/enterprise)
- currency (USD/EUR/GBP/UZS/RUB, default USD)
- theme (light/dark/auto)
- is_active, is_verified
- **13 fields total, 4 indexes**

### User (users.models.User) — extends AbstractUser
- No username field — uses email as USERNAME_FIELD
- email (unique), first_name, last_name, phone
- role (SUPER_ADMIN/COMPANY_ADMIN/MANAGER/STAFF/VIEWER)
- company (FK to Company)
- profile_picture, date_of_birth, address, city, country
- is_active, is_deleted (soft delete), deleted_at
- last_password_change
- **Methods**: soft_delete(), restore(), is_super_admin(), is_company_admin(), is_manager(), is_staff_user(), is_viewer(), has_company_access()
- **9 indexes**

### Product (products.models.Product)
- company (FK), name, sku (auto-generated, unique), barcode, qr_code
- category (electronics/clothing/food/furniture/tools/other)
- quantity, price
- description, supplier, image
- batch_number, expiration_date
- shelf, rack, section
- created_at, updated_at
- **Properties**: is_low_stock, stock_status, is_expired, is_expiring_soon
- Auto-generates SKU, barcode image, QR code on save
- **11 indexes**

### Transaction (inventory.models.Transaction)
- company (FK), product (FK), transaction_type (IN/OUT)
- quantity, user (FK), notes, created_at
- **6 indexes**

### CustomerDebt (finance.models.CustomerDebt)
- company (FK), customer_name, phone_number
- debt_amount, paid_amount (default 0)
- due_date, notes, payment_status (unpaid/partial/paid/overdue)
- created_by (FK), created_at, updated_at
- **6 indexes**

### SupplierDebt (finance.models.SupplierDebt)
- company (FK), supplier_name
- amount_owed, paid_amount (default 0)
- due_date, notes, payment_status
- created_by (FK), created_at, updated_at
- **6 indexes**

### Payment (finance.models.Payment)
- company (FK), payment_type (customer/supplier)
- customer_debt (FK, nullable), supplier_debt (FK, nullable)
- amount, payment_date, notes
- created_by (FK), created_at
- **5 indexes**

### Activity (activity.models.Activity)
- company (FK), activity_type (15 types)
- description, user (FK)
- related_object_type, related_object_id
- created_at
- **4 indexes**

---

## URL Structure

| URL | App | View | Auth Required |
|-----|-----|------|---------------|
| `/` | inventory | dashboard | Yes |
| `/login/` | warehouse_system | custom_login | No |
| `/logout/` | warehouse_system | custom_logout | Yes |
| `/register/` | users | register | No |
| `/products/` | products | product_list | Yes |
| `/products/create/` | products | product_create | Yes |
| `/products/<pk>/edit/` | products | product_update | Yes |
| `/products/<pk>/delete/` | products | product_delete | Yes |
| `/products/<pk>/barcode/` | products | product_barcode | Yes |
| `/products/<pk>/qrcode/` | products | product_qrcode | Yes |
| `/transactions/` | inventory | transaction_list | Yes |
| `/stock-in/` | inventory | stock_in | Yes |
| `/stock-out/` | inventory | stock_out | Yes |
| `/business-insights/` | inventory | business_insights | Yes |
| `/finance/` | finance | financial_dashboard | Yes |
| `/finance/customer-debts/` | finance | customer_debt_list | Yes |
| `/finance/customer-debts/create/` | finance | customer_debt_create | Yes |
| `/finance/customer-debts/<pk>/` | finance | customer_debt_detail | Yes |
| `/finance/customer-debts/<pk>/update/` | finance | customer_debt_update | Yes |
| `/finance/customer-debts/<pk>/delete/` | finance | customer_debt_delete | Yes |
| `/finance/supplier-debts/` | finance | supplier_debt_list | Yes |
| `/finance/supplier-debts/create/` | finance | supplier_debt_create | Yes |
| `/finance/supplier-debts/<pk>/` | finance | supplier_debt_detail | Yes |
| `/finance/supplier-debts/<pk>/update/` | finance | supplier_debt_update | Yes |
| `/finance/supplier-debts/<pk>/delete/` | finance | supplier_debt_delete | Yes |
| `/finance/payments/<type>/<id>/create/` | finance | payment_create | Yes |
| `/finance/customer-profiles/<name>/` | finance | customer_profile | Yes |
| `/finance/supplier-profiles/<name>/` | finance | supplier_profile | Yes |
| `/activity/` | activity | activity_timeline | Yes |
| `/users/profile/` | users | profile | Yes |
| `/users/change-password/` | users | change_password | Yes |
| `/users/password-reset/` | users | password_reset_request | No |
| `/users/reset/<uidb64>/<token>/` | users | password_reset_confirm | No |
| `/users/employees/` | users | employee_list | Yes |
| `/users/employees/create/` | users | employee_create | Yes |
| `/users/employees/<pk>/update/` | users | employee_update | Yes |
| `/users/employees/<pk>/delete/` | users | employee_delete | Yes |
| `/users/employees/<pk>/reset-password/` | users | employee_reset_password | Yes |

---

## What Works

1. Full product CRUD with company isolation
2. Stock IN/OUT transactions with validation
3. Company registration and multi-tenant data isolation
4. Employee management (create/update/delete/reset password)
5. Customer and supplier debt management
6. Payment processing
7. Activity logging for most operations
8. Dashboard with statistics and charts
9. Business insights page with analytics
10. Dark/Light theme toggle
11. Mobile responsive sidebar
12. Search, filter, sort, pagination across all list views
13. Barcode and QR code generation
14. Soft delete for employees
15. Session timeout (30 minutes)
16. Brute-force protection (django-axes)

---

## What Is Partially Implemented

1. **Password reset emails** — Email sending is commented out
2. **API endpoints** — DRF installed but no API routes wired (source files deleted, only .pyc remain)
3. **Role-based decorators** — Defined but NOT used on most views
4. **User/Company admin registration** — NOT in Django admin
5. **Company dashboard/settings templates** — Templates exist but NOT linked from URLs
6. **Transaction list search/filter** — Just displays paginated list, no search

---

## What Is Broken / Bugs

1. **Transaction.save() double-counting** — Updates product quantity on every save including edits, causing incorrect stock counts
2. **Payment.save() double-counting** — Increments paid_amount on every save including edits
3. **Activity.log_activity() missing company** — Activities created via this method have company=None, breaking company-scoped filtering
4. **Dashboard chart hardcoded data** — Transaction chart shows `[12, 19, 3, 5, 2, 3, 7]` instead of real data
5. **Financial dashboard chart calculation** — Incorrect arithmetic on aggregated totals
6. **Profile template errors** — References form.role and form.email which don't exist in UserUpdateForm
7. **Profile template URL error** — References `company_dashboard` URL which is not defined
8. **Employee list JS errors** — References element IDs that don't exist in HTML
9. **Missing requirements.txt** — No dependency documentation
10. **axes/lockout.html template** — Referenced in settings but doesn't exist
11. **script.js is unrelated** — Contains portfolio website code, not warehouse functionality
12. **activity.0004 migration mismatch** — Adds ip_address/user_agent fields that don't exist in model

---

## What Must NOT Be Touch

1. **Database file (db.sqlite3)** — Contains existing data, must be preserved
2. **Company model structure** — UUID PK, multi-tenant foundation
3. **User model structure** — Email-based auth, role system
4. **Company isolation pattern** — ForeignKey-based filtering works correctly
5. **Migration history** — Must not be squashed or deleted
6. **Existing product data** — SKUs, barcodes, QR codes
7. **Existing finance data** — Debt records, payment history

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 4.2+ |
| Python | 3.13 |
| Database | SQLite (PostgreSQL ready) |
| Auth | Custom User + django-axes |
| Frontend | Django Templates + Bootstrap 5.3 |
| Icons | Bootstrap Icons 1.10.0 |
| Charts | Chart.js 4.4.0 |
| Barcode | python-barcode (Code128) |
| QR | qrcode |
| Images | Pillow |
| API (inactive) | djangorestframework |
| Filter (inactive) | django-filter |
| Session | 30-min timeout |
| Language | Uzbek (primary) |
