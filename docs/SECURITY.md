# SKLAT PRO — Security Documentation

## Authentication
- **Login**: Custom view with django-axes brute-force protection
- **Password Policy**: 4 validators (length, complexity, similarity, common)
- **Session**: Secure cookies in production, session expiry configured
- **Rate Limiting**: Login (20 req/min), API (100 req/min), per-IP

## Authorization
- **Roles**: SUPER_ADMIN, COMPANY_ADMIN, MANAGER, STAFF, etc.
- **Per-Module Permissions**: products, inventory, sales, finance, etc.
- **Backend Enforcement**: All views use `@login_required`; company-scoped queries

## Multi-Tenancy
- **CompanyMiddleware**: Redirects users without company assignment
- **TenantMiddleware**: Sets `request.tenant` for scoped queries
- **Isolation**: All business queries filter by `company` FK
- **Verified**: Cross-tenant data leakage test passed (20 checks, 10 modules)

## CSRF Protection
- All POST forms include `{% csrf_token %}`
- No `@csrf_exempt` decorators anywhere in the project
- Login view explicitly decorated with `@csrf_protect`

## XSS Protection
- Django template auto-escaping enabled by default
- User input rendered through templates (not raw HTML)
- X-XSS-Protection header set

## Security Headers (6 active)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
- `X-Request-ID: <uuid>` (request tracing)

## Production Requirements
- Set `DJANGO_DEBUG=False`
- Set strong `DJANGO_SECRET_KEY` (64+ chars)
- Configure `DJANGO_ALLOWED_HOSTS`
- Enable SSL/HTTPS
- Set `SESSION_COOKIE_SECURE=True`
- Set `CSRF_COOKIE_SECURE=True`
