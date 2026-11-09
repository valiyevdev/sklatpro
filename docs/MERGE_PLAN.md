# MERGE PLAN — Old System + New SKLAT PRO = Unified System

## Principle

The old project is the foundation. The new SKLAT PRO requirements are the evolution. Every existing module is mapped to the new architecture. Nothing is deleted — everything is extended, improved, and visually unified.

---

## Module Mapping

### OLD: Dashboard (inventory/views.py — dashboard)
### NEW: Dashboard
- **Preserve**: Total products, low stock, recent transactions, stock in/out charts, category distribution
- **Add**: Total stock, inventory value, purchases, sales, gross profit, customer debt, supplier debt
- **Add**: Sales vs Purchases chart, Profit Trend, Inventory Trend, Top Products, Sales by Category, Warehouse Distribution
- **Add**: Widgets — Low Stock, Recent Activities, Pending Orders, Pending Purchases, Pending Transfers, Overdue Payments, Supplier Debts
- **Add**: Quick actions — New Product, New Purchase, New Sale, New Transfer, New Order, New List, New Customer, New Supplier, Record Payment, Scan Barcode
- **Add**: Role-adaptive content
- **Fix**: Hardcoded chart data → real data from database

### OLD: Products (products/)
### NEW: Products Module
- **Preserve**: Product model (name, sku, barcode, qr_code, category, quantity, price, description, supplier, image, batch_number, expiration_date, shelf/rack/section)
- **Preserve**: Barcode/QR generation
- **Preserve**: Product CRUD, search, filter, pagination
- **Extend model**: Add brand, unit (pcs/kg/g/liter/ml/meter/cm/m2/m3/box/pack/pallet/set/custom), sale_price, min_stock, max_stock, tax, weight, dimensions, warehouse FK, status, notes
- **Add**: Product variants (size, color, storage, etc.)
- **Add**: Categories management (separate model)
- **Add**: Brands management (separate model)
- **Add**: Units management (separate model)
- **Add**: Import/Export (Excel, CSV)
- **Add**: Bulk actions
- **Add**: Column visibility toggle
- **New URLs**: /products/categories/, /products/brands/, /products/units/, /products/variants/, /products/import/

### OLD: Inventory (inventory/)
### NEW: Inventory Module
- **Preserve**: Transaction model (IN/OUT), stock validation
- **Fix**: Transaction.save() double-counting bug — use F() expressions and atomic operations
- **Extend model**: Add movement_type (Opening Stock/Purchase/Sale/Transfer In/Transfer Out/Adjustment/Return/Damage/Loss), reference, warehouse FK, reason
- **Add**: Stock movements list (dedicated, auditable)
- **Add**: Low stock alerts page
- **Add**: Inventory adjustments
- **Add**: Inventory count
- **Add**: Inventory overview (per-warehouse breakdown)
- **New URLs**: /inventory/overview/, /inventory/movements/, /inventory/low-stock/, /inventory/adjustments/, /inventory/count/

### OLD: Warehouses (NEW — does not exist)
### NEW: Warehouses Module
- **Create**: Warehouse model (name, code, address, phone, manager FK, is_active)
- **Create**: Warehouse dashboard (Total Products, Total Stock, Stock Value, Low Stock, Incoming, Outgoing, Transfers)
- **Create**: Transfer model (from_warehouse, to_warehouse, status: Draft/Pending/Approved/In Transit/Completed/Cancelled)
- **Create**: Transfer items
- **Create**: Transfer workflow views
- **New URLs**: /warehouses/, /warehouses/<pk>/, /warehouses/transfers/, /warehouses/transfers/create/, /warehouses/transfers/<pk>/

### OLD: Purchases / Incoming (NEW — partially exists as stock_in)
### NEW: Purchases Module
- **Preserve**: Stock IN transaction logic, company isolation
- **Create**: Purchase model (supplier FK, warehouse FK, reference, date, products M2M, total, payment_status, currency, status: Draft/Pending/Approved/Received/Partially Received/Cancelled)
- **Create**: PurchaseItem model (product, quantity, unit_price, discount, tax, total)
- **Create**: Supplier model (name, company, phone, email, telegram, address, balance, notes)
- **Create**: Purchase views (CRUD, receiving workflow)
- **Fix**: Receiving must update inventory, create movement, create activity
- **New URLs**: /purchases/, /purchases/create/, /purchases/<pk>/, /purchases/suppliers/

### OLD: Sales / Outgoing (NEW — partially exists as stock_out)
### NEW: Sales Module
- **Preserve**: Stock OUT transaction logic, stock validation
- **Create**: Sale model (customer FK, warehouse FK, reference, date, products M2M, total, payment_status, currency, status: Draft/Confirmed/Packed/Shipped/Completed/Cancelled/Returned)
- **Create**: SaleItem model (product, quantity, unit_price, discount, tax, total)
- **Create**: Customer model (name, company, phone, email, telegram, address, balance, notes)
- **Create**: Sale views (CRUD, status workflow)
- **Fix**: Stock OUT must create proper movement records
- **New URLs**: /sales/, /sales/create/, /sales/<pk>/, /sales/customers/

### OLD: Orders (NEW — does not exist)
### NEW: Orders Module
- **Create**: Order model (customer, warehouse, reference, date, items, total, status: Draft/Pending/Confirmed/Processing/Packed/Shipped/Completed/Cancelled)
- **Create**: OrderItem model
- **Create**: Order views
- **New URLs**: /orders/, /orders/create/, /orders/<pk>/

### OLD: Lists / Spiskalar (NEW — does not exist)
### NEW: Lists Module
- **Create**: List model (name, type: Picking/Shipping/Restock/Inventory Count/Purchase/Custom, assigned_to FK, priority, due_date, notes, status, progress)
- **Create**: ListItem model (product, quantity, completed, completed_at, notes)
- **Create**: List views (CRUD, completion workflow, mobile-optimized)
- **New URLs**: /lists/, /lists/create/, /lists/<pk>/, /lists/<pk>/complete/<item_pk>/

### OLD: Contacts (NEW — partially exists as customer/supplier names in finance)
### NEW: Contacts Module
- **Preserve**: Existing customer_name/supplier_name data
- **Create**: Contact model (name, company, type: Customer/Supplier/Employee/Other, phone, email, telegram, address, balance, debt, notes)
- **Create**: Contact profile view (orders, purchases, sales, payments, activity)
- **Create**: Contact views (CRUD, search, filter)
- **Migration**: Import existing customer/supplier names into Contact model
- **New URLs**: /contacts/, /contacts/create/, /contacts/<pk>/

### OLD: Finance (finance/)
### NEW: Finance Module
- **Preserve**: CustomerDebt, SupplierDebt, Payment models, all CRUD views
- **Fix**: Payment.save() double-counting bug
- **Add**: Income model, Expense model, Transaction model (generic financial transaction)
- **Add**: Finance dashboard with charts (Income vs Expenses, Cash Flow, Receivables/Payables)
- **Add**: Receivables page, Payables page
- **Add**: Currency support (UZS default, USD, EUR, RUB configurable)
- **New URLs**: /finance/income/, /finance/expenses/, /finance/transactions/, /finance/receivables/, /finance/payables/

### OLD: Reports (NEW — partially exists as business_insights)
### NEW: Reports Module
- **Preserve**: Business insights analytics data
- **Create**: Dedicated reports for Sales, Purchases, Inventory, Stock Movement, Profit, Finance, Warehouse, Customer, Supplier, Employee Activity
- **Add**: Date/warehouse/product/category/customer/supplier/employee filters
- **Add**: Export (Excel, CSV, PDF)
- **New URLs**: /reports/sales/, /reports/purchases/, /reports/inventory/, /reports/profit/, /reports/finance/, /reports/warehouse/

### OLD: Users (users/)
### NEW: Users / Roles / Permissions Module
- **Preserve**: User model, Company model, authentication, employee management
- **Preserve**: Login/logout, password change/reset
- **Fix**: Password reset email sending
- **Add**: Granular permissions system (products.view, products.create, etc.)
- **Add**: Permission-based views (not just role-based)
- **Add**: User activity log per user
- **Add**: Session management
- **New URLs**: /users/roles/, /users/permissions/, /users/sessions/

### OLD: Activity (activity/)
### NEW: Notifications + Audit Module
- **Preserve**: Activity model, timeline view, role-based filtering
- **Fix**: Activity.log_activity() missing company parameter
- **Add**: Notification model (low stock, new order, payment overdue, etc.)
- **Add**: Notification views (list, mark read, preferences)
- **Add**: Audit log model (user, action, object, before/after state)
- **New URLs**: /notifications/, /notifications/<pk>/read/, /audit/

### OLD: Barcode/QR (products/views.py)
### NEW: Barcode / QR Module
- **Preserve**: Barcode generation (Code128), QR generation
- **Add**: Barcode scan workflow (mobile-first)
- **Add**: QR scan workflow
- **Add**: Search by barcode/QR
- **Add**: Bulk barcode/QR generation
- **New URLs**: /scanner/, /barcodes/generate/, /qrcodes/generate/

### OLD: Import/Export (NEW — does not exist)
### NEW: Import/Export Module
- **Create**: Import flow (Upload → Mapping → Preview → Validation → Error reporting → Confirmation → Import)
- **Create**: Export flow (Filter → Format selection → Generate → Download)
- **Support**: Excel, CSV
- **New URLs**: /import/products/, /import/customers/, /import/suppliers/, /export/

---

## New Modules To Create From Scratch

| Module | Priority | Dependencies |
|--------|----------|-------------|
| Warehouses + Transfers | HIGH | Products |
| Purchases + Suppliers | HIGH | Products, Warehouses |
| Sales + Customers | HIGH | Products, Warehouses |
| Orders | MEDIUM | Products, Customers |
| Lists / Spiskalar | MEDIUM | Products, Orders |
| Contacts | HIGH | None (extends existing) |
| Notifications | MEDIUM | All modules |
| Audit Logs | MEDIUM | All modules |
| Reports | MEDIUM | All modules |
| Import/Export | MEDIUM | All modules |
| Barcode/QR Scanner | LOW | Products |
| Settings | HIGH | Company |

---

## Design System Merge

The entire application will be visually unified using a single design system:

- **Sidebar**: Dark (#1e293b), clean navigation, collapsible on mobile
- **Topbar**: White/light, search, notifications bell, user avatar, company name
- **Content**: White surfaces, consistent card/table/form styles
- **Colors**: Blue/Indigo primary (#4f46e5), Green success, Amber warning, Red danger, Neutral grays
- **Typography**: Clean sans-serif, strong hierarchy
- **Components**: Unified buttons, inputs, tables, badges, cards, modals, drawers, tooltips, toasts
- **Responsive**: Intentional design for 1440+, 1200, 1024, 768, 480, 390, 360px
- **Theme**: Light mode + Dark mode with CSS custom properties

---

## Implementation Order

1. Fix critical bugs (Transaction.save, Payment.save, Activity.log_activity)
2. Create unified design system (CSS custom properties, component styles)
3. Global app shell (sidebar, topbar, responsive navigation)
4. Authentication modernization (login/register UI)
5. Dashboard redesign
6. Products redesign + new fields
7. Inventory redesign + stock movements
8. Warehouses + Transfers
9. Purchases + Incoming
10. Sales + Outgoing
11. Orders
12. Lists / Spiskalar
13. Contacts
14. Finance
15. Reports
16. Users / Roles / Permissions
17. Notifications / Audit
18. Barcode / QR Scanner
19. Import / Export
20. Mobile optimization
21. Dark mode
22. Localization (Uzbek → Russian → English)
23. Performance optimization
24. Security review
