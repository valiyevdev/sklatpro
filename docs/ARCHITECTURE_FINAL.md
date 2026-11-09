# SKLAT PRO — Architecture Document

## Tech Stack
- **Backend**: Django 5.2, Python 3.13
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Frontend**: Django templates, Bootstrap Icons 1.11
- **Auth**: django-axes 8.3 (brute-force protection)
- **Cache**: Django locmem (dev) / Redis (production)
- **Background Jobs**: Python threading (no Celery)

## Application Structure (23 Apps)
| App | Purpose |
|-----|---------|
| users | Authentication, company management, RBAC |
| products | Product catalog, categories, brands, variants |
| inventory | Stock levels, transactions, adjustments, counts |
| warehouses | Multi-warehouse, zones, locations, WMS operations |
| purchases | Purchase orders, receiving, supplier returns |
| sales | Sales, returns, payments, customer management |
| orders | Order lifecycle, fulfillment, reservations |
| crm | Customer 360, segments, tags, tasks, communications |
| pricing | Price lists, discounts, promotions |
| finance | Transactions, payments, debts, accounts |
| pos | POS terminals, shifts, receipts, cash management |
| spiskalar | Task management, work management |
| reports | Business intelligence, analytics, exports |
| markings | Product marking, GTIN, traceability |
| logistics | Shipments, vehicles, drivers, routes, delivery |
| ecommerce | Multi-channel commerce, marketplace integration |
| integrations | Third-party API integrations, webhooks |
| automation | Business rule engine, automated workflows |
| sklat_ai | AI assistant, insights, forecasts, recommendations |
| saas_platform | Platform admin, subscriptions, RBAC, audit |
| documents | Document management, templates, generation |
| storefront | Online store, cart, checkout |
| notifications | In-app notifications |

## Multi-Tenancy Architecture
```
Request → TenantMiddleware → sets request.tenant
        → CompanyMiddleware → redirects if no company
        → View → _get_company(request) → filters by company FK
```

## Authentication Flow
```
Login → axes (brute-force check) → authenticate() → login()
      → AuditLog entry → redirect to dashboard
```

## Design System
- CSS variables for theming (dark/light)
- Component classes: card-pro, btn-pro, table-pro, badge-pro, stat-card
- 4-language localization: uz, uz_cyr, ru, en
- Template tag: `{% t "key" %}` for translations
