# SKLAT PRO — Known Issues

## HIGH Priority
| # | Issue | Impact | Mitigation |
|---|-------|--------|------------|
| 1 | No file upload validation (type/size) | DoS, potential RCE | Add FileExtensionValidator + MAX_UPLOAD_SIZE |

## MEDIUM Priority
| # | Issue | Impact | Mitigation |
|---|-------|--------|------------|
| 2 | N+1 queries in POS product search | Slow search with 20+ products | Pre-fetch stock levels into dict |
| 3 | N+1 in RFM analysis | Slow reports with many customers | Rewrite as single annotated query |
| 4 | Customer @property methods run individual queries | Slow CRM lists | Use prefetch_related in views |
| 5 | Missing DB indexes on logistics, CRM, POS models | Slow queries on large datasets | Add class Meta.indexes |
| 6 | Superuser without company falls back to Company.objects.first() | Silent wrong-company scoping | Warning message added; should assign company |
| 7 | Storefront duplicate OnlineCart records | MultipleObjectsReturned crash | .filter().first() used as workaround |
| 8 | Naive datetime warnings in Sale.created_at | Potential timezone bugs | Use timezone-aware datetimes |

## LOW Priority
| # | Issue | Impact | Mitigation |
|---|-------|--------|------------|
| 9 | DEBUG defaults to True | Exposes debug info in production | Set DJANGO_DEBUG=False |
| 10 | Bare except clauses in storefront (3) | Masks real errors | Change to except Exception |
| 11 | Wildcard imports in 3 files | Namespace pollution | Replace with explicit imports |
| 12 | Unused imports in 6 files | Code clutter | Remove unused imports |

## COSMETIC
| # | Issue | Impact |
|---|-------|--------|
| 13 | `__import__` in ecommerce/views.py | Fixed (replaced with proper import) |

## Resolved in Phase 23
- [x] Ecommerce 500 crash (Order not imported)
- [x] Warehouse/Users URL double-prefix
- [x] CRM IDOR on delete/update (7 views fixed)
- [x] Storefront MultipleObjectsReturned
- [x] Bare except clauses (storefront)
- [x] Unused imports (6 files)
- [x] Wildcard imports (3 files)
- [x] SECRET_KEY hardcoded fallback
- [x] Superuser Company.objects.first() (warning added)
