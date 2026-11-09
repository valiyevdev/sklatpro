# ARCHITECTURE — SKLAT PRO Unified System

## Technology Stack (Preserved)

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend | Django 4.2+ | Keep existing |
| Python | 3.13 | Keep existing |
| Database | SQLite → PostgreSQL | SQLite for dev, PostgreSQL for production |
| Auth | Custom User + django-axes | Keep existing |
| Frontend | Django Templates + Bootstrap 5 | Redesign with new design system |
| Icons | Bootstrap Icons | Keep existing |
| Charts | Chart.js 4.4 | Keep existing |
| Barcode | python-barcode | Keep existing |
| QR | qrcode | Keep existing |
| Images | Pillow | Keep existing |
| API | djangorestframework | Reactivate for future SPA migration |
| Filter | django-filter | Reactivate for API |

---

## Application Architecture

```
sklat_pro/
├── warehouse_system/          # Main Django project (KEEP)
│   ├── settings.py
│   ├── urls.py
│   ├── views.py              # Login/Logout
│   ├── middleware.py          # CompanyMiddleware
│   └── wsgi.py
│
├── core/                     # NEW — shared utilities
│   ├── mixins.py             # CompanyMixin, PermissionMixin
│   ├── permissions.py        # Granular permission classes
│   ├── utils.py              # Pagination, search, export helpers
│   ├── validators.py         # Shared validators
│   └── templatetags/         # Custom template tags
│       └── core_tags.py      # has_perm, currency_format, etc.
│
├── users/                    # KEEP — extend
│   ├── models.py             # Company, User (KEEP)
│   ├── views.py              # Extend with roles/permissions
│   ├── forms.py              # Extend
│   ├── urls.py               # Extend
│   ├── decorators.py         # KEEP + add permission decorators
│   ├── middleware.py          # KEEP
│   └── admin.py              # Register models
│
├── products/                 # KEEP — extend heavily
│   ├── models.py             # Extend: brand, unit, sale_price, min/max stock, tax, weight, dimensions, status
│   ├── views.py              # Extend: variants, categories, brands, units, import/export
│   ├── forms.py              # Extend
│   ├── urls.py               # Extend
│   └── admin.py              # Extend
│
├── inventory/                # KEEP — extend + fix bugs
│   ├── models.py             # Extend: movement_type, warehouse, reference, reason
│   ├── views.py              # Extend: movements, low stock, adjustments, count
│   ├── forms.py              # Extend
│   ├── urls.py               # Extend
│   └── admin.py              # Extend
│
├── warehouses/               # NEW
│   ├── models.py             # Warehouse, Transfer, TransferItem
│   ├── views.py              # Warehouse dashboard, transfer workflow
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── purchases/                # NEW (evolves from stock_in)
│   ├── models.py             # Purchase, PurchaseItem, Supplier
│   ├── views.py              # Purchase CRUD, receiving
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── sales/                    # NEW (evolves from stock_out)
│   ├── models.py             # Sale, SaleItem, Customer
│   ├── views.py              # Sale CRUD, status workflow
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── orders/                   # NEW
│   ├── models.py             # Order, OrderItem
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── lists/                    # NEW — Spiskalar
│   ├── models.py             # List, ListItem
│   ├── views.py              # CRUD, completion, mobile-optimized
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── contacts/                 # NEW (evolves from customer/supplier names)
│   ├── models.py             # Contact
│   ├── views.py              # CRUD, profiles
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── finance/                  # KEEP — extend
│   ├── models.py             # KEEP: CustomerDebt, SupplierDebt, Payment + ADD: Income, Expense, Transaction
│   ├── views.py              # Extend: income, expenses, cash flow
│   ├── forms.py              # Extend
│   ├── urls.py               # Extend
│   └── admin.py              # Extend
│
├── reports/                  # NEW
│   ├── views.py              # Report views with filters and exports
│   ├── urls.py
│   └── utils.py              # Report generation, export helpers
│
├── activity/                 # KEEP — fix + extend
│   ├── models.py             # Fix company bug + ADD: AuditLog model
│   ├── views.py              # Extend
│   ├── urls.py               # Extend
│   └── admin.py              # Extend
│
├── notifications/            # NEW
│   ├── models.py             # Notification model
│   ├── views.py              # CRUD, mark read
│   ├── forms.py
│   ├── urls.py
│   └── admin.py
│
├── scanner/                  # NEW — Barcode/QR
│   ├── views.py              # Scan, search by barcode
│   └── urls.py
│
├── import_export/            # NEW
│   ├── views.py              # Import/Export flows
│   ├── forms.py
│   ├── urls.py
│   └── utils.py              # CSV/Excel parsers
│
├── templates/                # REDESIGN — unified design system
│   ├── base.html             # Global app shell (sidebar + topbar)
│   ├── components/           # Reusable component templates
│   │   ├── sidebar.html
│   │   ├── topbar.html
│   │   ├── table.html
│   │   ├── card.html
│   │   ├── modal.html
│   │   ├── form.html
│   │   ├── pagination.html
│   │   ├── empty_state.html
│   │   ├── loading.html
│   │   └── toast.html
│   ├── registration/
│   ├── dashboard/
│   ├── products/
│   ├── inventory/
│   ├── warehouses/
│   ├── purchases/
│   ├── sales/
│   ├── orders/
│   ├── lists/
│   ├── contacts/
│   ├── finance/
│   ├── reports/
│   ├── users/
│   ├── notifications/
│   └── scanner/
│
├── static/
│   ├── css/
│   │   ├── design-system.css    # NEW — unified design tokens + components
│   │   ├── layout.css           # NEW — sidebar, topbar, responsive
│   │   ├── components.css       # NEW — buttons, inputs, tables, cards, etc.
│   │   ├── pages.css            # NEW — page-specific styles
│   │   ├── dark.css             # NEW — dark mode overrides
│   │   └── responsive.css       # NEW — breakpoint-specific styles
│   ├── js/
│   │   ├── app.js               # NEW — global app logic
│   │   ├── sidebar.js           # NEW — sidebar toggle, mobile nav
│   │   ├── search.js            # NEW — global search
│   │   ├── scanner.js           # NEW — barcode/QR scanning
│   │   └── charts.js            # NEW — chart configurations
│   └── images/                  # Icons, logos
│
├── media/                       # KEEP existing
├── db.sqlite3                   # KEEP
├── manage.py                    # KEEP
└── requirements.txt             # NEW — document dependencies
```

---

## Data Flow

### Authentication Flow
```
User → Login (email + password) → django-axes check → Session created → CompanyMiddleware checks company → Dashboard
```

### Product Creation Flow
```
User → Product Form → Validation → Product.save() → Auto-generate SKU + Barcode + QR → Activity logged → Redirect
```

### Stock Movement Flow
```
User → Stock IN/OUT Form → Transaction.save() → Product.quantity updated (atomic) → Movement record created → Activity logged
```

### Purchase Flow
```
User → Create Purchase → Supplier + Warehouse + Items → Save as Draft → Approve → Receive → Stock updated → Movements created → Activity logged
```

### Sale Flow
```
User → Create Sale → Customer + Warehouse + Items → Save as Draft → Confirm → Stock validated → Complete → Movements created → Activity logged → Payment recorded
```

### Transfer Flow
```
User → Create Transfer → From Warehouse + To Warehouse + Items → Submit → Approve → In Transit → Complete → Stock adjusted in both warehouses
```

---

## Multi-Tenancy Architecture

### Isolation Strategy
- **Application-level**: Every model has `company` ForeignKey
- **Query-level**: Every view filters by `request.user.company`
- **Middleware-level**: CompanyMiddleware ensures company association
- **Superuser bypass**: Superusers see all data (for platform admin)

### Data Isolation Pattern
```python
# Every list view follows this pattern:
def model_list(request):
    company = request.user.company
    if not company and not request.user.is_superuser:
        return redirect('profile')
    
    queryset = Model.objects.filter(company=company)
    if request.user.is_superuser:
        queryset = Model.objects.all()
    
    # ... process queryset
```

---

## Permission Architecture

### Role Hierarchy
```
SUPER_ADMIN > COMPANY_ADMIN > MANAGER > STAFF > VIEWER
```

### Permission Format
```
module.action
```

### Examples
```
products.view
products.create
products.edit
products.delete
inventory.view
inventory.adjust
inventory.transfer
purchases.view
purchases.create
purchases.approve
sales.view
sales.create
sales.refund
finance.view
finance.create
finance.approve
reports.view
reports.export
users.view
users.create
users.edit
users.delete
```

### Enforcement
- Backend: Decorators + permission checks in views
- Frontend: Template tags to show/hide UI elements
- API: DRF permission classes

---

## Template Architecture

### Base Template Hierarchy
```
base.html
├── components/sidebar.html
├── components/topbar.html
└── block content → page template
```

### Component System
All pages use shared components:
- Tables (sortable, filterable, paginated)
- Cards (stat cards, content cards)
- Forms (consistent validation, layout)
- Modals (confirmation, forms)
- Drawers (mobile navigation, detail panels)
- Toasts (success/error/info notifications)
- Badges (status, role)
- Empty states
- Loading skeletons

---

## Settings Architecture

### Company-Level Settings (per company)
- Company profile (name, logo, address)
- Currency (UZS, USD, EUR, RUB)
- Timezone (default: Asia/Tashkent)
- Theme (light/dark)
- Low stock threshold
- Notification preferences
- Tax rate

### Platform-Level Settings (super admin)
- Subscription plans
- Feature flags
- System notifications
- Backup configuration
