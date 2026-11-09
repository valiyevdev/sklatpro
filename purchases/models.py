from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from users.models import Company


class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    telegram = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name

    @property
    def total_purchases(self):
        return self.purchases.aggregate(
            total=models.Sum('total')
        )['total'] or 0

    @property
    def total_paid(self):
        return self.purchases.filter(payment_status='paid').aggregate(
            total=models.Sum('total')
        )['total'] or 0

    @property
    def total_unpaid(self):
        return self.purchases.exclude(payment_status='paid').aggregate(
            total=models.Sum('total')
        )['total'] or 0

    @property
    def purchase_count(self):
        return self.purchases.count()

    @property
    def overdue_count(self):
        from django.utils import timezone
        return self.purchases.filter(
            payment_status__in=['unpaid', 'partial'],
            expected_delivery_date__lt=timezone.now().date()
        ).count()


class Purchase(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('partially_received', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    PAYMENT_TERMS_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('net7', 'Net 7'),
        ('net15', 'Net 15'),
        ('net30', 'Net 30'),
        ('net60', 'Net 60'),
        ('prepaid', 'Prepaid'),
    ]
    CURRENCY_CHOICES = [
        ('UZS', 'UZS'),
        ('USD', 'USD'),
        ('RUB', 'RUB'),
    ]

    VALID_TRANSITIONS = {
        'draft': ['pending_approval', 'cancelled'],
        'pending_approval': ['approved', 'cancelled'],
        'approved': ['ordered', 'cancelled'],
        'ordered': ['partially_received', 'received', 'cancelled'],
        'partially_received': ['partially_received', 'received', 'returned'],
        'received': ['returned'],
        'cancelled': [],
        'returned': [],
    }

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchases')
    reference = models.CharField(max_length=50)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchases')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='purchases')
    order_date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='cod')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UZS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchases_created')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.supplier.name}"

    def clean(self):
        if self.status and self.status != 'draft' and not self.pk:
            if self.items.count() == 0:
                raise ValidationError('Purchase must have at least one item.')

    def can_transition(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status):
        if not self.can_transition(new_status):
            raise ValidationError(
                f"Cannot transition from '{self.status}' to '{new_status}'. "
                f"Allowed: {self.VALID_TRANSITIONS.get(self.status, [])}"
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

    def calculate_total(self):
        total = sum(item.total for item in self.items.all())
        self.total = total - self.discount + self.tax
        self.save(update_fields=['total', 'updated_at'])

    @property
    def total_ordered(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_received(self):
        return sum(item.received_quantity for item in self.items.all())

    @property
    def total_remaining(self):
        return self.total_ordered - self.total_received

    @property
    def total_damaged(self):
        return sum(item.damaged_quantity for item in self.items.all())

    @property
    def total_rejected(self):
        return sum(item.rejected_quantity for item in self.items.all())

    @property
    def receiving_progress(self):
        if self.total_ordered == 0:
            return 0
        return round((self.total_received / self.total_ordered) * 100, 1)

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.expected_delivery_date and self.status in ('ordered', 'partially_received'):
            return self.expected_delivery_date < timezone.now().date()
        return False

    @property
    def days_overdue(self):
        from django.utils import timezone
        if self.is_overdue:
            return (timezone.now().date() - self.expected_delivery_date).days
        return 0


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.unit_price) - self.discount + self.tax
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity

    @property
    def is_fully_received(self):
        return self.received_quantity >= self.quantity

    @property
    def receiving_difference(self):
        return self.received_quantity - self.quantity

    @property
    def effective_received(self):
        return self.received_quantity - self.damaged_quantity - self.rejected_quantity


class PurchaseReturn(models.Model):
    REASON_CHOICES = [
        ('damaged', 'Damaged'),
        ('wrong_product', 'Wrong Product'),
        ('quality_issue', 'Quality Issue'),
        ('overage', 'Overage'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchase_returns')
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='returns')
    reference = models.CharField(max_length=50)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reason_notes = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return {self.reference} - {self.purchase.reference}"

    def calculate_total(self):
        total = sum(item.quantity * item.unit_price for item in self.items.all())
        self.total = total
        self.save(update_fields=['total', 'updated_at'])


class PurchaseReturnItem(models.Model):
    return_order = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='items')
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
