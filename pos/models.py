from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid


class POSTerminal(models.Model):
    """POS Terminal/Register"""
    TERMINAL_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    ]

    company = models.ForeignKey(
        'users.Company',
        on_delete=models.CASCADE,
        related_name='pos_terminals'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.CASCADE,
        related_name='pos_terminals'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=TERMINAL_STATUS_CHOICES, default='active')
    receipt_printer = models.CharField(max_length=100, blank=True, null=True)
    cash_drawer = models.BooleanField(default=True)
    barcode_scanner = models.BooleanField(default=True)
    card_terminal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    default_payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Transfer'),
        ('online', 'Online'),
        ('other', 'Other'),
    ], default='cash')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'POS Terminal'
        verbose_name_plural = 'POS Terminals'

    def __str__(self):
        return f"{self.name} ({self.code})"

    def to_dict(self):
        return {
            'id': self.pk,
            'name': self.name,
            'code': self.code,
            'serial_number': self.serial_number,
            'status': self.status,
            'warehouse_id': self.warehouse_id,
            'warehouse_name': self.warehouse.name if self.warehouse else None,
            'cash_drawer': self.cash_drawer,
            'barcode_scanner': self.barcode_scanner,
            'card_terminal': self.card_terminal,
            'default_payment_method': self.default_payment_method,
        }


class CashShift(models.Model):
    """Cash Shift - tracks opening and closing of cash drawer"""
    SHIFT_STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    company = models.ForeignKey(
        'users.Company',
        on_delete=models.CASCADE,
        related_name='cash_shifts'
    )
    terminal = models.ForeignKey(
        POSTerminal,
        on_delete=models.CASCADE,
        related_name='shifts'
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cash_shifts'
    )
    shift_number = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=SHIFT_STATUS_CHOICES, default='open')
    opening_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    closing_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_cash_shifts'
    )

    class Meta:
        ordering = ['-opened_at']
        verbose_name = 'Cash Shift'
        verbose_name_plural = 'Cash Shifts'

    def __str__(self):
        return f"Shift {self.shift_number} - {self.cashier.get_full_name() or self.cashier.username}"

    def close_shift(self, closing_amount, expected_amount=None):
        """Close the shift and calculate difference"""
        self.closing_amount = closing_amount
        self.expected_amount = expected_amount
        if expected_amount is not None:
            self.difference = closing_amount - expected_amount
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()

    def to_dict(self):
        return {
            'id': self.pk,
            'shift_number': self.shift_number,
            'status': self.status,
            'cashier_id': self.cashier_id,
            'cashier_name': self.cashier.get_full_name() or self.cashier.username,
            'terminal_id': self.terminal_id,
            'terminal_name': self.terminal.name if self.terminal else None,
            'opening_amount': str(self.opening_amount),
            'closing_amount': str(self.closing_amount) if self.closing_amount is not None else None,
            'expected_amount': str(self.expected_amount) if self.expected_amount is not None else None,
            'difference': str(self.difference) if self.difference is not None else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'notes': self.notes,
        }


class POSReceipt(models.Model):
    """POS Receipt - represents a completed POS transaction"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Transfer'),
        ('online', 'Online'),
        ('other', 'Other'),
        ('mixed', 'Mixed'),
    ]

    company = models.ForeignKey(
        'users.Company',
        on_delete=models.CASCADE,
        related_name='pos_receipts'
    )
    terminal = models.ForeignKey(
        POSTerminal,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    shift = models.ForeignKey(
        CashShift,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    receipt_number = models.CharField(max_length=50, unique=True)
    reference = models.CharField(max_length=50, blank=True, null=True)
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_receipts'
    )
    sale = models.OneToOneField(
        'sales.Sale',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pos_receipt'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.CASCADE,
        related_name='pos_receipts'
    )
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ], default='draft')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    change = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='UZS')
    coupon_code = models.CharField(max_length=50, blank=True, default='')
    discount_reason = models.CharField(max_length=200, blank=True, default='')
    loyalty_points_earned = models.PositiveIntegerField(default=0)
    loyalty_points_redeemed = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_pos_receipts'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'POS Receipt'
        verbose_name_plural = 'POS Receipts'

    def __str__(self):
        return f"Receipt {self.receipt_number}"

    def calculate_total(self):
        """Recalculate total from items"""
        items = self.items.all()
        self.subtotal = sum(item.line_total for item in items)
        self.tax_amount = self.subtotal * (self.tax_rate / Decimal('100'))
        self.total = self.subtotal + self.tax_amount - self.discount_amount
        self.save()

    def complete(self, payment_method, amount_paid):
        """Complete the receipt"""
        self.payment_method = payment_method
        self.amount_paid = amount_paid
        self.change = amount_paid - self.total
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def cancel(self):
        """Cancel the receipt"""
        self.status = 'cancelled'
        self.save()

    def to_dict(self):
        return {
            'id': self.pk,
            'receipt_number': self.receipt_number,
            'reference': self.reference,
            'status': self.status,
            'payment_method': self.payment_method,
            'subtotal': str(self.subtotal),
            'tax_rate': str(self.tax_rate),
            'tax_amount': str(self.tax_amount),
            'discount_amount': str(self.discount_amount),
            'total': str(self.total),
            'amount_paid': str(self.amount_paid),
            'change': str(self.change),
            'currency': self.currency,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'terminal_id': self.terminal_id,
            'terminal_name': self.terminal.name if self.terminal else None,
            'shift_id': self.shift_id,
            'shift_number': self.shift.shift_number if self.shift else None,
            'coupon_code': self.coupon_code,
            'discount_reason': self.discount_reason,
            'loyalty_points_earned': self.loyalty_points_earned,
            'loyalty_points_redeemed': self.loyalty_points_redeemed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'items': [item.to_dict() for item in self.items.all()],
        }


class POSReceiptItem(models.Model):
    """POS Receipt Line Item"""
    receipt = models.ForeignKey(
        POSReceipt,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='pos_receipt_items'
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_receipt_items'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('1'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'POS Receipt Item'
        verbose_name_plural = 'POS Receipt Items'

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    def save(self, *args, **kwargs):
        """Calculate line total before saving"""
        self.line_total = (self.unit_price * self.quantity) - self.discount + self.tax
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            'id': self.pk,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'product_sku': self.product.sku if self.product else None,
            'product_barcode': self.product.barcode if self.product else None,
            'variant_id': self.variant_id,
            'variant_name': self.variant.name if self.variant else None,
            'quantity': str(self.quantity),
            'unit_price': str(self.unit_price),
            'discount': str(self.discount),
            'tax': str(self.tax),
            'line_total': str(self.line_total),
            'unit_symbol': self.product.unit.symbol if self.product and self.product.unit else None,
        }


class CashMovement(models.Model):
    """Cash drawer movements: sale cash in, refund, cash in, cash out"""
    MOVEMENT_TYPES = [
        ('opening', 'Opening Cash'),
        ('sale_cash', 'Sale Cash'),
        ('refund', 'Refund'),
        ('cash_in', 'Cash In'),
        ('cash_out', 'Cash Out'),
        ('closing', 'Closing'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='cash_movements')
    shift = models.ForeignKey(CashShift, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount}"


class HeldSale(models.Model):
    """Held/parked sales - stored temporarily"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='held_sales')
    terminal = models.ForeignKey(POSTerminal, on_delete=models.SET_NULL, null=True, blank=True, related_name='held_sales')
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='held_sales')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    ticket_number = models.CharField(max_length=20)
    name = models.CharField(max_length=120, blank=True, default='')
    cart_data = models.JSONField(default=dict)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    held_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-held_at']

    def __str__(self):
        return f"Held Sale {self.ticket_number}"


class POSReturn(models.Model):
    """POS returns/refunds"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='pos_returns')
    original_receipt = models.ForeignKey(POSReceipt, on_delete=models.CASCADE, related_name='returns')
    return_number = models.CharField(max_length=50, unique=True)
    terminal = models.ForeignKey(POSTerminal, on_delete=models.CASCADE)
    shift = models.ForeignKey(CashShift, on_delete=models.CASCADE)
    refund_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('account_credit', 'Account Credit'),
    ])
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField(blank=True)
    condition = models.CharField(max_length=20, choices=[
        ('sellable', 'Sellable'),
        ('quarantine', 'Quarantine'),
        ('damaged', 'Damaged'),
    ], default='sellable')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return {self.return_number}"


class POSReturnItem(models.Model):
    """POS Return Line Item"""
    pos_return = models.ForeignKey(POSReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
