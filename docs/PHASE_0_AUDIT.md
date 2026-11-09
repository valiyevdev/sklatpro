# PHASE 0 AUDIT - SKLAT PRO Implementation Baseline

**Date:** August 17, 2026
**Status:** COMPLETE

---

## 1. Current Technology Stack

### Backend
- Framework: Django 4.2.7, Python 3.13
- ORM: Django ORM
- Auth: Custom User model (email-based, extends AbstractUser)
- API: Django REST Framework 3.14 (installed, minimally used)
- Brute-force: django-axes 6.0
- Filters: django-filter 23.0

### Frontend
- Template Engine: Django Templates (76 .html files)
- Design System: Custom static/css/design-system.css (811 lines, CSS custom properties)
- Icons: Bootstrap Icons CDN
- Fonts: Inter (Google Fonts)
- Charts: Chart.js (referenced in dashboard)
- JavaScript: Vanilla JS, minimal

### Database
- Engine: SQLite 3 (db.sqlite3)
- PostgreSQL: Config prepared but commented out
- Status: All migrations applied (0 unapplied)

### Libraries
- python-barcode >=0.15 (Code128 barcode generation)
- qrcode >=7.4 (QR code generation)
- Pillow >=10.0 (Image processing)

### Infrastructure
- Docker: None
- Redis: None
- Celery: None
- Nginx: None
- WSGI: Django built-in

---

## 2. Current Architecture

```
warehouse_system/          # Project config (settings, urls, wsgi)
core/                  # Translation system, middleware, context processors
users/                 # Company + User models, auth, employee management
products/              # Product CRUD, barcode/QR generation
inventory/             # Dashboard, stock IN/OUT transactions
warehouses/            # Warehouse CRUD, inter-warehouse transfers
purchases/             # Purchase orders, supplier management
sales/                 # Sales orders, customer management
orders/                # Separate order module
spiskalar/             # Task/picking lists
contacts/              # Unified contact management
finance/               # Customer/supplier debts, payments
reports/               # Basic report pages
activity/              # Activity timeline/audit log
notifications/         # In-app notifications
scanner/               # Barcode/QR scanner
import_export/         # CSV import/export
templates/             # 76 HTML templates
static/                # CSS (design-system.css, custom.css)
media/                 # Uploaded files (products, qr_codes)
db.sqlite3             # SQLite database
```

Architecture: Monolithic Django with template-based frontend. Each module is a separate Django app. No REST API layer actively used (DRF installed but no API views defined). Server-side rendering with Django templates.

---

## 3. Application Run Status

All 17 pages return 200 OK. manage.py check passes with 0 issues. All migrations applied. Media files serve correctly. All 4 languages (UZ Latin, UZ Cyrillic, Russian, English) work end-to-end.

### Known Runtime Issues
1. axes/lockout.html missing - will cause 500 if lockout triggers
2. Password reset email sending commented out - view says "link sent" but no email sent
3. Activity 0004 migration adds fields not in model (dead migration)
4. script.js in project root contains unrelated portfolio code
5. custom.css exists alongside design-system.css - potential conflicts

---

## 4. Module Audit

| Module | Status | Notes |
|--------|--------|-------|
| Dashboard | WORKING | Stats, charts, low stock alerts, recent transactions |
| Authentication | PARTIAL | Login/logout work, password reset broken (email not sent) |
| Users | WORKING | Registration, profile, employee CRUD |
| Roles | WORKING | 5 roles defined, role checks in views |
| Permissions | PARTIAL | Role checks exist but decorators unused |
| Companies | WORKING | Company model with UUID PK, subscription plans |
| Products | WORKING | Full CRUD, barcode, QR code, image upload |
| Categories | PARTIAL | Hardcoded choices in model (6 categories) |
| Brands | MISSING | No brand model |
| Suppliers | WORKING | CRUD via purchases app |
| Customers | WORKING | CRUD via sales app |
| Inventory | WORKING | Stock IN/OUT, transaction history, dashboard stats |
| Warehouses | WORKING | CRUD + inter-warehouse transfers |
| Purchases | WORKING | Purchase orders, receive flow |
| Sales | WORKING | Sale orders with status workflow |
| Orders | WORKING | Separate order module |
| Finance | WORKING | Customer/supplier debts, payment tracking |
| Reports | PARTIAL | Basic pages, no real report generation |
| Notifications | WORKING | Model + list view, limited creation |
| Activity Logs | WORKING | Timeline view with filtering |
| Settings | PARTIAL | Company settings model, limited UI |
| Import/Export | PARTIAL | CSV import/export (basic) |
| Barcode/QR | WORKING | Auto-generation on product save |
| Responsive UI | PARTIAL | Design system exists, not fully responsive |
| Localization | PARTIAL | Custom 4-language system, some hardcoded strings |

---

## 5. Product Module Audit

### Model Fields
company(FK), name, sku(unique), category(choices), quantity, price, description, supplier(CharField not FK), image, barcode, qr_code, batch_number, expiration_date, shelf, rack, section

### Image Upload - All Working
Model ImageField, Form FileInput, Template enctype, View request.FILES, MEDIA_URL/MEDIA_ROOT, Dev serving, JS image preview, 4 existing media files

### Issues
- Supplier is CharField, not FK to Supplier model
- No brand field, no product variants
- SKU uniqueness is global (not per-company)
- Hardcoded category choices (no Category model)

---

## 6. Database Audit

All 17 business models have company FK for multi-tenant isolation. Current data: 7 users, 6 companies, 2 products (both with company=None), 14 activity logs. Everything else is empty.

Data quality: 2 products have company=None, 1 user has company=None.

---

## 7. Multi-Tenancy Audit

ForeignKey-based isolation on every business model. Most views filter at queryset level. Some views (products, finance) use manual post-fetch checks (TOCTOU risk).

### Risks
1. IDOR in stock_in/stock_out: Product not company-filtered on POST
2. IDOR in sale_create: Product not company-filtered on POST
3. Products with null company (2 existing)
4. Middleware uses hardcoded URL strings
5. No API-level isolation

---

## 8. Authentication & Authorization

Login/logout/session working. Password reset BROKEN (email commented out). django-axes for brute-force. 5 roles (SUPER_ADMIN, COMPANY_ADMIN, MANAGER, STAFF, VIEWER). Custom decorators exist but are never used. No permission framework.

---

## 9. Inventory Logic

Stock IN/OUT via Transaction model. Transaction.save() auto-updates product quantity via F() expressions. Dashboard shows stats. No purchase/sale integration with stock yet. No stock reservations.

Critical bug: Sale status completion deducts stock but can be called multiple times (double deduction).

---

## 10. Finance

CustomerDebt + SupplierDebt + Payment models. Manual debt tracking (not linked to purchases/sales). Payment creates payment record and updates debt paid_amount. Status auto-calculated.

---

## 11. Responsive Design

design-system.css has responsive breakpoints. Base template uses sidebar layout. Not fully tested at all breakpoints (360px-1440px).

---

## 12. Localization

Custom 4-language system (UZ Latin, UZ Cyrillic, Russian, English). Template tags, middleware, context processor, session+cookie persistence, AJAX language switcher. 360+ translation keys. Some hardcoded strings remain in Python views and JavaScript.

---

## 13. Media / File Upload

MEDIA_URL=/media/, MEDIA_ROOT=BASE_DIR/media. Dev serving via static(). Product images upload correctly. QR codes auto-generated. No file size limits configured. No image validation beyond Pillow.

---

## 14. API Audit

DRF installed but NO API views defined. No serializers. No API URL patterns. All functionality is via Django template views. DRF settings configured (session auth, page pagination, 20 items/page).

---

## 15. Security

- SECRET_KEY hardcoded (django-insecure-...)
- DEBUG=True
- ALLOWED_HOSTS=[] (empty)
- CSRF protection enabled
- Session cookie HttpOnly, SameSite=Lax
- 30-min session timeout
- Password validators configured
- XSS filter enabled
- Content type nosniff enabled
- XFrameOptions DENY
- SSL redirect OFF (dev mode)
- No rate limiting beyond axes
- No CORS configuration
- File uploads: no size limit, no validation

---

## 16. Performance

- N+1 risk: Dashboard low_stock_products uses separate queries
- No select_related/prefetch_related in most list views
- SQLite in production (not suitable for concurrent writes)
- No caching configured (Redis/Memcached)
- No background job processing
- No CDN for static files

---

## 17-18. Feature Gap Analysis & Mapping

| Future Feature | Current Status | Path |
|----------------|---------------|------|
| Dashboard | EXISTS | inventory/ dashboard view |
| Products | EXISTS | products/ full CRUD |
| Product Variants | MISSING | - |
| Inventory | EXISTS | inventory/ stock IN/OUT |
| Multi-Warehouse | EXISTS | warehouses/ CRUD + transfers |
| WMS | MISSING | - |
| Purchases | EXISTS | purchases/ CRUD + receive |
| Sales | EXISTS | sales/ CRUD + status |
| Orders | EXISTS | orders/ CRUD |
| Lists/Tasks | EXISTS | spiskalar/ basic lists |
| CRM | MISSING | contacts/ is basic |
| Contacts | EXISTS | contacts/ basic CRUD |
| Pricing | MISSING | Single price per product |
| Discounts | PARTIAL | Discount field on purchase/sale |
| Promotions | MISSING | - |
| Finance | EXISTS | finance/ debts + payments |
| POS | MISSING | - |
| Reports | PARTIAL | reports/ basic pages |
| Business Intelligence | MISSING | - |
| ABC/XYZ Analysis | MISSING | - |
| RFM | MISSING | - |
| Forecasting | MISSING | - |
| Marking/Traceability | PARTIAL | Barcode/QR on products |
| Electronic Documents | MISSING | - |
| Logistics | MISSING | - |
| E-commerce | MISSING | - |
| Integrations | MISSING | - |
| Automation | MISSING | - |
| AI | MISSING | - |
| Multi-company SaaS | EXISTS | Company model + FK isolation |
| Roles/Permissions | PARTIAL | 5 roles, no permission framework |
| Mobile Workflows | MISSING | No PWA, no mobile optimization |
| Barcode/QR | EXISTS | Auto-generation + scanner |
| Import/Export | EXISTS | CSV import/export (basic) |
| Multi-language | EXISTS | 4-language custom system |
| Dark Mode | EXISTS | CSS variables, theme switcher |

---

## 19. DO NOT CHANGE

1. Company model (users/models.py Company class)
2. User model (users/models.py User class)
3. Database (db.sqlite3) - preserve all data
4. Existing migrations - do not recreate
5. Existing URL patterns - extend, don't replace
6. Working product CRUD
7. Working stock IN/OUT logic (Transaction.save)
8. Working auth flow (login/logout/register)
9. Company isolation pattern (ForeignKey)
10. Existing translation keys in core/translations.py

---

## 20. Critical Bugs to Fix First

1. **CRITICAL:** Stock double-deduction in sale_update_status (sales/views.py)
2. **CRITICAL:** IDOR in stock_in/stock_out (product not company-filtered on POST)
3. **CRITICAL:** IDOR in sale_create (product not company-filtered)
4. **HIGH:** Password reset broken (email not sent)
5. **HIGH:** No form validation on POST (raw request.POST.get in warehouses, purchases, sales, orders)
6. **MEDIUM:** No state machine for status transitions
7. **MEDIUM:** Race condition in reference generation
8. **LOW:** axes/lockout.html template missing
9. **LOW:** Dead decorators in users/decorators.py

---

## 21. Recommended Implementation Order

1. Fix critical security bugs (IDOR, stock deduction)
2. Fix password reset
3. Add missing axes/lockout.html template
4. Unify design system across all templates
5. Complete 4-language system (remaining hardcoded strings)
6. Add Category/Brand models
7. Link Product.supplier FK to Supplier model
8. Add permission framework
9. Build out Reports/BI
10. Add POS
11. Add API layer (DRF viewsets)
12. Add PWA/mobile optimization
