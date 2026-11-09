from django.conf import settings
from django.db import models
from django.db.models import F, Sum, Q
from products.models import Product
from users.models import Company


class Transaction(models.Model):
    """Legacy transaction model — preserved for backward compatibility."""
    TRANSACTION_TYPES = [
        ('IN', 'Stock IN'),
        ('OUT', 'Stock OUT'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_transactions', null=True, blank=True, verbose_name="Company")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Product")
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES, verbose_name="Type")
    quantity = models.PositiveIntegerField(verbose_name="Quantity")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="User")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.product.name} ({self.quantity})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            if self.transaction_type == 'IN':
                Product.objects.filter(pk=self.product_id).update(quantity=F('quantity') + self.quantity)
            else:
                Product.objects.filter(pk=self.product_id).update(quantity=F('quantity') - self.quantity)
            self.product.refresh_from_db()


# ============================================================
# PHASE 5 — INVENTORY MOVEMENT ENGINE
# ============================================================

class StockLevel(models.Model):
    """Per-warehouse stock level. Source of truth for warehouse stock."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_levels')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='stock_levels')
    quantity = models.IntegerField(default=0, verbose_name="On Hand")
    reserved = models.IntegerField(default=0, verbose_name="Reserved")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'product', 'warehouse']
        verbose_name = "Stock Level"
        verbose_name_plural = "Stock Levels"
        indexes = [
            models.Index(fields=['company', 'product']),
            models.Index(fields=['company', 'warehouse']),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.quantity}"

    @property
    def available(self):
        return max(0, self.quantity - self.reserved)

    @property
    def stock_status(self):
        if self.quantity <= 0:
            return 'out_of_stock'
        if self.quantity <= self.product.min_stock:
            return 'low_stock'
        if self.quantity >= self.product.max_stock:
            return 'overstock'
        return 'in_stock'


class StockMovement(models.Model):
    """Immutable audit log of every stock change."""

    DIRECTION_IN = 'IN'
    DIRECTION_OUT = 'OUT'
    DIRECTION_CHOICES = [
        (DIRECTION_IN, 'In'),
        (DIRECTION_OUT, 'Out'),
    ]

    MOVEMENT_TYPES = [
        ('opening', 'Opening Stock'),
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('return_in', 'Customer Return'),
        ('return_out', 'Supplier Return'),
        ('adjustment_increase', 'Adjustment Increase'),
        ('adjustment_decrease', 'Adjustment Decrease'),
        ('damage', 'Damage'),
        ('loss', 'Loss'),
        ('found', 'Found'),
        ('correction', 'Correction'),
        ('stock_in', 'Stock IN'),
        ('stock_out', 'Stock OUT'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField()
    before_quantity = models.IntegerField(default=0, verbose_name="Stock Before")
    after_quantity = models.IntegerField(default=0, verbose_name="Stock After")
    reference_type = models.CharField(max_length=50, blank=True, verbose_name="Ref Type")
    reference_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="Ref ID")
    reference_number = models.CharField(max_length=50, blank=True, verbose_name="Ref Number")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        indexes = [
            models.Index(fields=['company', 'product']),
            models.Index(fields=['company', 'warehouse']),
            models.Index(fields=['company', 'movement_type']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.direction} {self.product.name} x{self.quantity}"


class StockAdjustment(models.Model):
    """Stock adjustment header."""
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_adjustments')
    reference = models.CharField(max_length=50, unique=True)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='stock_adjustments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_adjustments')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_adjustments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Stock Adjustment"
        verbose_name_plural = "Stock Adjustments"
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"ADJ-{self.reference} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            count = StockAdjustment.objects.filter(company=self.company).count() + 1
            self.reference = f"ADJ-{count:04d}"
        super().save(*args, **kwargs)


class StockAdjustmentItem(models.Model):
    """Line item in a stock adjustment."""
    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    expected_quantity = models.IntegerField(default=0, verbose_name="Expected")
    actual_quantity = models.IntegerField(default=0, verbose_name="Actual")
    difference = models.IntegerField(default=0, verbose_name="Difference")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Adjustment Item"
        verbose_name_plural = "Adjustment Items"

    def __str__(self):
        return f"{self.product.name}: {self.expected_quantity} -> {self.actual_quantity}"

    def save(self, *args, **kwargs):
        self.difference = self.actual_quantity - self.expected_quantity
        super().save(*args, **kwargs)


class InventoryCount(models.Model):
    """Stocktake / physical inventory count."""
    STATUS_DRAFT = 'draft'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='inventory_counts')
    reference = models.CharField(max_length=50, unique=True)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='inventory_counts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_counts')
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_counts')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_counts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inventory Count"
        verbose_name_plural = "Inventory Counts"
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"COUNT-{self.reference} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            count = InventoryCount.objects.filter(company=self.company).count() + 1
            self.reference = f"COUNT-{count:04d}"
        super().save(*args, **kwargs)

    @property
    def total_items(self):
        return self.items.count()

    @property
    def counted_items(self):
        return self.items.filter(actual_quantity__isnull=False).exclude(actual_quantity='').count()

    @property
    def total_differences(self):
        return self.items.filter(difference__gt=0).count() + self.items.filter(difference__lt=0).count()

    @property
    def progress_pct(self):
        total = self.total_items
        if total == 0:
            return 0
        return int((self.counted_items / total) * 100)


class InventoryCountItem(models.Model):
    """Line item in an inventory count / stocktake."""
    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    expected_quantity = models.IntegerField(default=0, verbose_name="Expected")
    actual_quantity = models.IntegerField(null=True, blank=True, verbose_name="Actual")
    difference = models.IntegerField(default=0, verbose_name="Difference")
    barcode_scanned = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Count Item"
        verbose_name_plural = "Count Items"

    def __str__(self):
        actual = self.actual_quantity if self.actual_quantity is not None else '?'
        return f"{self.product.name}: {self.expected_quantity} -> {actual}"

    def save(self, *args, **kwargs):
        if self.actual_quantity is not None:
            self.difference = self.actual_quantity - self.expected_quantity
        super().save(*args, **kwargs)


# ============================================================
# STOCK ENGINE — Central stock management functions
# ============================================================

class StockEngine:
    """Central stock calculation engine."""

    @staticmethod
    def default_warehouse(company):
        """Return the warehouse used for stock entered without a warehouse."""
        from warehouses.models import Warehouse

        return Warehouse.objects.filter(
            company=company, is_active=True
        ).order_by('-is_main', 'id').first()

    @staticmethod
    def get_stock_level(product, warehouse, company):
        """Get or create stock level for a product/warehouse/company."""
        level, _ = StockLevel.objects.get_or_create(
            company=company, product=product, warehouse=warehouse,
            defaults={'quantity': 0, 'reserved': 0}
        )
        return level

    @staticmethod
    def get_on_hand(product, company):
        """Total on-hand across all warehouses."""
        result = StockLevel.objects.filter(
            company=company, product=product
        ).aggregate(total=Sum('quantity'))
        return result['total'] or 0

    @staticmethod
    def get_reserved(product, company):
        """Total reserved across all warehouses."""
        result = StockLevel.objects.filter(
            company=company, product=product
        ).aggregate(total=Sum('reserved'))
        return result['total'] or 0

    @staticmethod
    def get_available(product, company):
        """Available = on_hand - reserved."""
        return max(0, StockEngine.get_on_hand(product, company) - StockEngine.get_reserved(product, company))

    @staticmethod
    def process_stock_change(product, warehouse, company, direction, movement_type,
                              quantity, user=None, reference_type='', reference_id=None,
                              reference_number='', reason='', notes=''):
        """
        Central stock change processor.
        Creates StockMovement, updates StockLevel, syncs Product.quantity.
        """
        from django.utils import timezone

        level = StockEngine.get_stock_level(product, warehouse, company)
        before = level.quantity

        if direction == 'IN':
            level.quantity += quantity
        else:
            level.quantity -= quantity
        level.save(update_fields=['quantity', 'last_updated'])

        after = level.quantity

        movement = StockMovement.objects.create(
            company=company,
            product=product,
            warehouse=warehouse,
            direction=direction,
            movement_type=movement_type,
            quantity=quantity,
            before_quantity=before,
            after_quantity=after,
            reference_type=reference_type,
            reference_id=reference_id,
            reference_number=reference_number,
            user=user,
            reason=reason,
            notes=notes,
        )

        StockEngine.sync_product_quantity(product, company)
        return movement

    @staticmethod
    def sync_product_quantity(product, company):
        """Sync Product.quantity with sum of all StockLevels."""
        total = StockLevel.objects.filter(
            company=company, product=product
        ).aggregate(total=Sum('quantity'))['total'] or 0
        Product.objects.filter(pk=product.pk).update(quantity=max(0, total))

    @staticmethod
    def sync_all_product_quantities(company):
        """Sync all product quantities for a company."""
        levels = StockLevel.objects.filter(company=company).values('product').annotate(
            total=Sum('quantity')
        )
        for item in levels:
            Product.objects.filter(pk=item['product']).update(
                quantity=max(0, item['total'])
            )

    @staticmethod
    def get_product_stock_summary(product, company):
        """Get complete stock summary for a product."""
        levels = StockLevel.objects.filter(
            company=company, product=product
        ).select_related('warehouse')
        total_on_hand = sum(l.quantity for l in levels)
        total_reserved = sum(l.reserved for l in levels)
        return {
            'product': product,
            'levels': levels,
            'total_on_hand': total_on_hand,
            'total_reserved': total_reserved,
            'total_available': max(0, total_on_hand - total_reserved),
            'min_stock': product.min_stock,
            'max_stock': product.max_stock,
            'stock_status': product.stock_status,
        }

    @staticmethod
    def get_inventory_overview(company):
        """Get inventory overview statistics.

        The three alert buckets come from the canonical Product classmethods
        so the dashboard tab counts always match the products' own
        `stock_status` and the three list views.
        """
        products = Product.objects.filter(company=company)
        total_products = products.count()
        total_value = sum(p.quantity * p.purchase_price for p in products if p.purchase_price)
        total_units = sum(p.quantity for p in products)
        low_stock = Product.low_stock_qs(company).count()
        out_of_stock = Product.out_of_stock_qs(company).count()
        overstock = Product.overstock_qs(company).count()
        total_reserved = StockLevel.objects.filter(company=company).aggregate(
            total=Sum('reserved'))['total'] or 0

        return {
            'total_products': total_products,
            'total_units': total_units,
            'total_value': total_value,
            'total_reserved': total_reserved,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'overstock': overstock,
        }

    @staticmethod
    def initialize_product_stock(product, warehouse, company, quantity, user=None, notes=''):
        """Set opening stock for a product in a warehouse."""
        level = StockEngine.get_stock_level(product, warehouse, company)
        if level.quantity == 0 and quantity > 0:
            level.quantity = quantity
            level.save(update_fields=['quantity', 'last_updated'])
            StockMovement.objects.create(
                company=company, product=product, warehouse=warehouse,
                direction='IN', movement_type='opening',
                quantity=quantity, before_quantity=0, after_quantity=quantity,
                user=user, reason='Opening Stock', notes=notes,
            )
            StockEngine.sync_product_quantity(product, company)
            return level
        elif level.quantity > 0:
            difference = quantity - level.quantity
            if difference != 0:
                direction = 'IN' if difference > 0 else 'OUT'
                StockEngine.process_stock_change(
                    product, warehouse, company, direction, 'correction',
                    abs(difference), user=user, reason='Opening Stock Correction', notes=notes
                )
            return level
        return level
