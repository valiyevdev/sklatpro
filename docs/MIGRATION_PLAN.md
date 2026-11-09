# MIGRATION PLAN — Database Schema Evolution

## Principles

1. **NEVER delete existing data** — all existing records must survive
2. **Additive migrations only** — add fields/tables, don't remove existing ones without data preservation
3. **Backward compatible** — old code paths must not break during migration
4. **Tested** — every migration must be tested with existing data
5. **Reversible** — where possible, provide reverse operations

---

## Phase 1: Critical Bug Fixes (No Schema Changes)

### 1.1 Fix Transaction.save() Double-Counting
**File**: `inventory/models.py`
**Change**: Modify save() to only update quantity on create, not on update
**Migration**: None needed (code change only)
**Risk**: Low — fixes incorrect behavior

### 1.2 Fix Payment.save() Double-Counting
**File**: `finance/models.py`
**Change**: Modify save() to only update paid_amount on create, not on update
**Migration**: None needed (code change only)
**Risk**: Low — fixes incorrect behavior

### 1.3 Fix Activity.log_activity() Missing Company
**File**: `activity/models.py`
**Change**: Add company parameter to log_activity() method
**Migration**: None needed (code change only)
**Risk**: Low — fixes broken functionality

---

## Phase 2: Product Model Extensions

### 2.1 Add New Product Fields
**File**: `products/models.py`
**Migration**: `products/0012_add_extended_fields.py`

```python
# New fields (all nullable for backward compatibility)
brand = ForeignKey('Brand', SET_NULL, null=True, blank=True)
unit = CharField(max_length=20, default='pcs', choices=UNIT_CHOICES)
sale_price = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
min_stock = PositiveIntegerField(default=0)
max_stock = PositiveIntegerField(null=True, blank=True)
tax = DecimalField(max_digits=5, decimal_places=2, default=0)
weight = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
length = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
width = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
height = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
warehouse = ForeignKey('warehouses.Warehouse', SET_NULL, null=True, blank=True)
status = CharField(max_length=20, default='active', choices=STATUS_CHOICES)
notes = TextField(blank=True)
```

**Data Migration**: 
- Set `sale_price` = `price` for all existing products (they had only one price)
- Set `status` = 'active' for all existing products
- Set `unit` = 'pcs' (default) for all existing products

**Risk**: Low — all fields are nullable or have defaults

### 2.2 Create Brand Model
**Migration**: `products/0013_create_brand_model.py`

```python
class Brand(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    slug = SlugField(max_length=200)
    logo = ImageField(upload_to='brands/', blank=True, null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Risk**: None — new table

### 2.3 Create Category Model
**Migration**: `products/0014_create_category_model.py`

```python
class Category(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    slug = SlugField(max_length=200)
    parent = ForeignKey('self', SET_NULL, null=True, blank=True)
    description = TextField(blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Data Migration**: 
- Create Category records from existing product category choices
- Update products to reference new Category FK
- Keep old `category` CharField as backup (rename to `old_category`)

**Risk**: Medium — requires data migration for existing products

### 2.4 Create Unit Model
**Migration**: `products/0015_create_unit_model.py`

```python
class Unit(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=50)
    abbreviation = CharField(max_length=10)
    base_unit = ForeignKey('self', SET_NULL, null=True, blank=True)
    conversion_factor = DecimalField(max_digits=10, decimal_places=4, default=1)
    is_active = BooleanField(default=True)
```

**Data Migration**: 
- Create default units (pcs, kg, g, liter, ml, meter, cm, m2, m3, box, pack, pallet, set)
- These are shared, not company-scoped

**Risk**: None — new table with defaults

---

## Phase 3: Warehouse System

### 3.1 Create Warehouse Model
**Migration**: `warehouses/0001_initial.py`

```python
class Warehouse(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    code = CharField(max_length=20)
    address = TextField(blank=True)
    phone = CharField(max_length=20, blank=True)
    manager = ForeignKey(User, SET_NULL, null=True, blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Data Migration**:
- Create default "Main Warehouse" for each existing company
- Update all existing products to reference this default warehouse

**Risk**: Medium — need to link existing data to warehouses

### 3.2 Create Transfer Models
**Migration**: `warehouses/0002_create_transfer_models.py`

```python
class Transfer(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    from_warehouse = ForeignKey(Warehouse, CASCADE, related_name='outgoing_transfers')
    to_warehouse = ForeignKey(Warehouse, CASCADE, related_name='incoming_transfers')
    status = CharField(max_length=20, default='draft')
    notes = TextField(blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    approved_by = ForeignKey(User, SET_NULL, null=True, related_name='approved_transfers')
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class TransferItem(Model):
    transfer = ForeignKey(Transfer, CASCADE, related_name='items')
    product = ForeignKey(Product, CASCADE)
    quantity = PositiveIntegerField()
    received_quantity = PositiveIntegerField(default=0)
    notes = TextField(blank=True)
```

**Risk**: None — new tables

---

## Phase 4: Purchases & Suppliers

### 4.1 Create Supplier Model
**Migration**: `purchases/0001_initial.py`

```python
class Supplier(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    contact_person = CharField(max_length=200, blank=True)
    phone = CharField(max_length=20, blank=True)
    email = EmailField(blank=True)
    telegram = CharField(max_length=100, blank=True)
    address = TextField(blank=True)
    balance = DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = TextField(blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Data Migration**:
- Import existing supplier names from Product model into Supplier records
- Update products to reference new Supplier FK

**Risk**: Medium — data migration for existing supplier names

### 4.2 Create Purchase Models
**Migration**: `purchases/0002_create_purchase_models.py`

```python
class Purchase(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    supplier = ForeignKey(Supplier, CASCADE)
    warehouse = ForeignKey(Warehouse, CASCADE)
    date = DateField(default=timezone.now)
    total = DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = CharField(max_length=20, default='unpaid')
    currency = CharField(max_length=3, default='UZS')
    status = CharField(max_length=20, default='draft')
    notes = TextField(blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class PurchaseItem(Model):
    purchase = ForeignKey(Purchase, CASCADE, related_name='items')
    product = ForeignKey(Product, CASCADE)
    quantity = PositiveIntegerField()
    unit_price = DecimalField(max_digits=10, decimal_places=2)
    discount = DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = DecimalField(max_digits=10, decimal_places=2, default=0)
    total = DecimalField(max_digits=12, decimal_places=2)
    received_quantity = PositiveIntegerField(default=0)
```

**Risk**: None — new tables

---

## Phase 5: Sales & Customers

### 5.1 Create Customer Model
**Migration**: `sales/0001_initial.py`

```python
class Customer(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    contact_person = CharField(max_length=200, blank=True)
    phone = CharField(max_length=20, blank=True)
    email = EmailField(blank=True)
    telegram = CharField(max_length=100, blank=True)
    address = TextField(blank=True)
    balance = DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = TextField(blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Data Migration**:
- Import existing customer names from CustomerDebt model into Customer records
- Update CustomerDebt to reference new Customer FK

**Risk**: Medium — data migration for existing customer names

### 5.2 Create Sale Models
**Migration**: `sales/0002_create_sale_models.py`

```python
class Sale(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    customer = ForeignKey(Customer, CASCADE)
    warehouse = ForeignKey(Warehouse, CASCADE)
    date = DateField(default=timezone.now)
    total = DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = CharField(max_length=20, default='unpaid')
    currency = CharField(max_length=3, default='UZS')
    status = CharField(max_length=20, default='draft')
    notes = TextField(blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class SaleItem(Model):
    sale = ForeignKey(Sale, CASCADE, related_name='items')
    product = ForeignKey(Product, CASCADE)
    quantity = PositiveIntegerField()
    unit_price = DecimalField(max_digits=10, decimal_places=2)
    discount = DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = DecimalField(max_digits=10, decimal_places=2, default=0)
    total = DecimalField(max_digits=12, decimal_places=2)
```

**Risk**: None — new tables

---

## Phase 6: Orders

### 6.1 Create Order Models
**Migration**: `orders/0001_initial.py`

```python
class Order(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    customer = ForeignKey(Customer, CASCADE)
    warehouse = ForeignKey(Warehouse, CASCADE)
    date = DateField(default=timezone.now)
    total = DecimalField(max_digits=12, decimal_places=2, default=0)
    status = CharField(max_length=20, default='draft')
    notes = TextField(blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class OrderItem(Model):
    order = ForeignKey(Order, CASCADE, related_name='items')
    product = ForeignKey(Product, CASCADE)
    quantity = PositiveIntegerField()
    unit_price = DecimalField(max_digits=10, decimal_places=2)
    total = DecimalField(max_digits=12, decimal_places=2)
```

**Risk**: None — new tables

---

## Phase 7: Lists (Spiskalar)

### 7.1 Create List Models
**Migration**: `lists/0001_initial.py`

```python
class List(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    type = CharField(max_length=20)  # picking/shipping/restock/inventory_count/purchase/custom
    assigned_to = ForeignKey(User, SET_NULL, null=True, blank=True)
    priority = CharField(max_length=10, default='medium')  # low/medium/high/urgent
    due_date = DateField(null=True, blank=True)
    notes = TextField(blank=True)
    status = CharField(max_length=20, default='pending')  # pending/in_progress/completed
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class ListItem(Model):
    list = ForeignKey(List, CASCADE, related_name='items')
    product = ForeignKey(Product, CASCADE)
    quantity = PositiveIntegerField()
    completed_quantity = PositiveIntegerField(default=0)
    completed = BooleanField(default=False)
    completed_at = DateTimeField(null=True, blank=True)
    notes = TextField(blank=True)
    order = ForeignKey('orders.Order', SET_NULL, null=True, blank=True)
```

**Risk**: None — new tables

---

## Phase 8: Contacts

### 8.1 Create Contact Model
**Migration**: `contacts/0001_initial.py`

```python
class Contact(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=200)
    type = CharField(max_length=20)  # customer/supplier/employee/other
    company_name = CharField(max_length=200, blank=True)
    phone = CharField(max_length=20, blank=True)
    email = EmailField(blank=True)
    telegram = CharField(max_length=100, blank=True)
    address = TextField(blank=True)
    balance = DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = TextField(blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Data Migration**:
- Import existing customer names from CustomerDebt
- Import existing supplier names from SupplierDebt
- Import existing employees from User model

**Risk**: Medium — data migration from multiple sources

---

## Phase 9: Finance Extensions

### 9.1 Add Income and Expense Models
**Migration**: `finance/0004_add_income_expense.py`

```python
class Income(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    category = CharField(max_length=50)
    amount = DecimalField(max_digits=12, decimal_places=2)
    date = DateField(default=timezone.now)
    description = TextField(blank=True)
    sale = ForeignKey('sales.Sale', SET_NULL, null=True, blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)

class Expense(Model):
    company = ForeignKey(Company, CASCADE)
    reference = CharField(max_length=50)
    category = CharField(max_length=50)
    amount = DecimalField(max_digits=12, decimal_places=2)
    date = DateField(default=timezone.now)
    description = TextField(blank=True)
    purchase = ForeignKey('purchases.Purchase', SET_NULL, null=True, blank=True)
    created_by = ForeignKey(User, SET_NULL, null=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Risk**: None — new tables

---

## Phase 10: Notifications & Audit

### 10.1 Create Notification Model
**Migration**: `notifications/0001_initial.py`

```python
class Notification(Model):
    company = ForeignKey(Company, CASCADE)
    user = ForeignKey(User, CASCADE, related_name='notifications')
    title = CharField(max_length=200)
    message = TextField()
    type = CharField(max_length=50)  # low_stock/new_order/payment_due/system
    read = BooleanField(default=False)
    related_object_type = CharField(max_length=50, blank=True)
    related_object_id = PositiveIntegerField(null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Risk**: None — new table

### 10.2 Create AuditLog Model
**Migration**: `activity/0005_create_audit_log.py`

```python
class AuditLog(Model):
    company = ForeignKey(Company, CASCADE)
    user = ForeignKey(User, SET_NULL, null=True)
    action = CharField(max_length=50)  # create/update/delete/view
    object_type = CharField(max_length=50)
    object_id = PositiveIntegerField()
    object_repr = CharField(max_length=200)
    changes = JSONField(default=dict)  # {field: [old, new]}
    ip_address = GenericIPAddressField(null=True, blank=True)
    user_agent = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Risk**: None — new table

---

## Phase 11: Product Variants

### 11.1 Create Variant Models
**Migration**: `products/0016_create_variant_models.py`

```python
class VariantAttribute(Model):
    company = ForeignKey(Company, CASCADE)
    name = CharField(max_length=100)  # e.g., "Size", "Color", "Storage"
    values = JSONField(default=list)  # ["S", "M", "L", "XL"]
    created_at = DateTimeField(auto_now_add=True)

class ProductVariant(Model):
    product = ForeignKey(Product, CASCADE, related_name='variants')
    sku = CharField(max_length=50, unique=True)
    barcode = CharField(max_length=100, blank=True)
    attributes = JSONField(default=dict)  # {"Size": "M", "Color": "Blue"}
    price = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = PositiveIntegerField(default=0)
    image = ImageField(upload_to='variants/', blank=True, null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Risk**: None — new tables, existing products remain as simple products

---

## Phase 12: Inventory Movement Enhancement

### 12.1 Enhance Transaction Model
**Migration**: `inventory/0004_enhance_transaction.py`

```python
# Add fields to existing Transaction model
movement_type = CharField(max_length=20, default='adjustment')
# Choices: opening_stock/purchase/sale/transfer_in/transfer_out/adjustment/return/damage/loss
reference = CharField(max_length=100, blank=True)
warehouse = ForeignKey('warehouses.Warehouse', SET_NULL, null=True, blank=True)
reason = TextField(blank=True)
```

**Data Migration**:
- For existing transactions with type='IN': set movement_type='purchase'
- For existing transactions with type='OUT': set movement_type='sale'
- Create default warehouse and assign to all existing transactions

**Risk**: Medium — modifies existing table, data migration required

---

## Migration Execution Order

1. Phase 1: Bug fixes (no migrations)
2. Phase 2: Product extensions
3. Phase 3: Warehouses (must come before inventory enhancement)
4. Phase 4: Purchases & Suppliers
5. Phase 5: Sales & Customers
6. Phase 6: Orders (depends on Sales)
7. Phase 7: Lists (depends on Orders)
8. Phase 8: Contacts (depends on Sales & Purchases)
9. Phase 9: Finance extensions
10. Phase 10: Notifications & Audit
11. Phase 11: Product Variants
12. Phase 12: Inventory enhancement (depends on Warehouses)

---

## Rollback Strategy

Each migration includes a `reverse()` operation:

- **New tables**: Drop table
- **New fields**: Remove field (after backing up data)
- **Data migrations**: Reverse data transformation (where possible)
- **Model changes**: Restore original model definition

**Emergency rollback**: Restore db.sqlite3 from backup before migration

---

## Testing Checklist

For each migration:
- [ ] Migration applies cleanly
- [ ] Migration reverses cleanly
- [ ] Existing data is preserved
- [ ] New fields have correct defaults
- [ ] Data migrations handle edge cases
- [ ] Foreign keys are properly set
- [ ] Indexes are created
- [ ] No data loss
- [ ] Application functions correctly after migration
