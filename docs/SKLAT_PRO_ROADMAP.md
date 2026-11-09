# SKLAT PRO Roadmap

## Phase 0 - Audit (COMPLETE)
- Full codebase audit
- Technology stack documentation
- Bug identification
- Feature gap analysis

## Phase 1 - Unified Design System
- Extend design-system.css to ALL templates
- Responsive design audit and fixes (360px-1440px)
- Dark mode consistency
- Mobile navigation
- Remove Bootstrap 5 remnants from registration pages
- Standardize all card/table/form patterns

## Phase 2 - 4-Language System
- Complete translation key coverage for all templates
- Python view message translation
- JavaScript translation dict
- Chart label translation
- Language switcher UX polish

## Phase 3 - Application Shell
- Fix critical security bugs (IDOR, stock deduction)
- Fix password reset flow
- Add axes/lockout.html template
- Clean up dead code (script.js, unused decorators)
- Unify URL namespacing
- Add form validation to all POST handlers

## Phase 4 - Products
- Add Category model (replace hardcoded choices)
- Add Brand model
- Link Product.supplier FK to Supplier model
- Product variants support
- Per-company SKU uniqueness
- Price tiers / cost tracking
- Product history/audit

## Phase 5 - Inventory
- Stock reservations
- Stock adjustments
- Returns processing
- Inventory count/audit
- Min/max stock levels per product
- Stock alerts automation
- Integration with purchases/sales

## Phase 6 - Warehouses + WMS
- Warehouse zones/sections
- Bin locations
- Transfer state machine
- Warehouse capacity tracking
- Warehouse-level stock views
- Pick/pack/ship workflow

## Phase 7 - Purchases
- Purchase order state machine
- Receiving workflow with verification
- Purchase returns
- Purchase templates/documents
- Supplier catalog
- Auto-reorder suggestions

## Phase 8 - Sales
- Sale state machine (prevent double stock deduction)
- Sales returns
- Invoice generation
- Receipt printing
- Sales quotes
- Customer pricing

## Phase 9 - Orders
- Order state machine
- Order-to-sale conversion
- Order tracking
- Partial fulfillment
- Back-order support

## Phase 10 - CRM + Contacts
- Contact interaction history
- Lead management
- Follow-up reminders
- Customer segmentation
- Communication log
- Contact merge

## Phase 11 - Pricing + Discounts
- Price lists / tiers
- Discount rules (percentage, fixed, BOGO)
- Promotions engine
- Seasonal pricing
- Customer-specific pricing
- Bulk pricing

## Phase 12 - Finance
- Income/expense tracking
- Profit & loss reports
- Cash flow analysis
- Bank reconciliation
- Multi-currency support
- Tax reports
- Financial dashboards

## Phase 13 - POS / Retail
- Point-of-sale interface
- Quick product scan
- Cash register
- Receipt printing
- Shift management
- Offline mode

## Phase 14 - Lists / Tasks
- Enhanced picking lists
- Task assignment
- Task workflows
- Priority management
- Due date tracking
- Task reporting

## Phase 15 - Reports / BI
- Sales analytics
- Purchase analytics
- Inventory analytics
- Financial reports
- ABC/XYZ analysis
- RFM analysis
- Trend charts
- Exportable reports
- Custom date ranges

## Phase 16 - Marking / Documents
- Product traceability
- Batch tracking
- Electronic invoices
- Delivery notes
- Purchase orders (documents)
- Custom document templates

## Phase 17 - Logistics
- Shipping integration
- Delivery tracking
- Route planning
- Carrier management
- Shipping cost calculation

## Phase 18 - E-commerce
- Product catalog API
- Online ordering
- Payment gateway integration
- Order management
- Customer portal

## Phase 19 - Integrations
- 1C integration
- SMS gateway
- Email service (SendGrid/Mailgun)
- Cloud storage (S3)
- Accounting software
- Marketplace APIs

## Phase 20 - Automation
- Auto-reorder triggers
- Stock alerts
- Scheduled reports
- Workflow automation
- Webhook support

## Phase 21 - AI
- Demand forecasting
- Smart reorder suggestions
- Price optimization
- Anomaly detection
- Natural language search

## Phase 22 - Security / SaaS / Scalability
- PostgreSQL migration
- Redis caching
- Celery background jobs
- API rate limiting
- Permission framework (object-level)
- Subscription management
- Tenant data isolation audit
- Performance optimization
- Load testing

## Phase 23 - Final QA / Production
- Full regression testing
- Security audit
- Performance benchmarking
- Deployment configuration
- Docker/containerization
- CI/CD pipeline
- Monitoring/alerting
- Documentation
