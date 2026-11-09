from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from users.models import Company


class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customers')
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

    # CRM Fields
    customer_type = models.CharField(max_length=20, choices=[('individual', 'Individual'), ('business', 'Business')], default='individual')
    customer_status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive'), ('blocked', 'Blocked'), ('prospect', 'Prospect'), ('lead', 'Lead')], default='active')
    website = models.URLField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_terms = models.CharField(max_length=20, choices=[('cod', 'Cash on Delivery'), ('prepaid', 'Prepaid'), ('net7', 'Net 7'), ('net15', 'Net 15'), ('net30', 'Net 30'), ('credit', 'Credit')], default='cod')
    assigned_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_customers')
    assigned_salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='salesperson_customers')
    rfm_recency = models.PositiveSmallIntegerField(null=True, blank=True)
    rfm_frequency = models.PositiveSmallIntegerField(null=True, blank=True)
    rfm_monetary = models.PositiveSmallIntegerField(null=True, blank=True)
    rfm_segment = models.CharField(max_length=30, blank=True)
    last_purchase_date = models.DateField(null=True, blank=True)
    total_lifetime_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name

    @property
    def total_sales(self):
        return self.sales.aggregate(total=models.Sum('total'))['total'] or 0

    @property
    def total_paid(self):
        return self.sales.filter(payment_status='paid').aggregate(
            total=models.Sum('total')
        )['total'] or 0

    @property
    def total_unpaid(self):
        return self.sales.exclude(payment_status='paid').aggregate(
            total=models.Sum('total')
        )['total'] or 0

    @property
    def sale_count(self):
        return self.sales.count()

    @property
    def overdue_count(self):
        from django.utils import timezone
        return self.sales.filter(
            payment_status__in=['unpaid', 'partial'],
            status__in=['confirmed', 'shipped', 'completed']
        ).count()

    @property
    def order_count(self):
        from orders.models import Order
        return Order.objects.filter(customer=self).count()

    @property
    def total_orders_value(self):
        from orders.models import Order
        return Order.objects.filter(customer=self).aggregate(t=models.Sum('total'))['t'] or 0

    @property
    def total_returns(self):
        return self.salereturn_set.aggregate(t=models.Sum('total'))['t'] or 0

    @property
    def return_count(self):
        return self.salereturn_set.count()

    @property
    def average_order_value(self):
        count = self.sale_count
        if count == 0:
            return 0
        return self.total_sales / count

    @property
    def outstanding_balance(self):
        debt_total = Debt.objects.filter(customer=self).exclude(status='paid').aggregate(
            t=models.Sum(models.F('total') - models.F('paid'))
        )['t'] or 0
        if debt_total:
            return debt_total
        return self.sales.exclude(payment_status='paid').aggregate(t=models.Sum('total'))['t'] or 0

    @property
    def active_orders(self):
        from orders.models import Order
        return Order.objects.filter(customer=self).exclude(
            status__in=['completed', 'cancelled', 'returned']
        ).count()

    @property
    def active_sales(self):
        return self.sales.exclude(
            status__in=['completed', 'cancelled', 'returned']
        ).count()


class Sale(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('reserved', 'Reserved'),
        ('picking', 'Picking'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
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
        ('prepaid', 'Prepaid'),
        ('net7', 'Net 7'),
        ('net15', 'Net 15'),
        ('net30', 'Net 30'),
        ('credit', 'Credit'),
    ]
    CURRENCY_CHOICES = [
        ('UZS', 'UZS'),
        ('USD', 'USD'),
        ('RUB', 'RUB'),
    ]

    VALID_TRANSITIONS = {
        'draft': ['confirmed', 'cancelled'],
        'confirmed': ['reserved', 'cancelled'],
        'reserved': ['picking', 'cancelled'],
        'picking': ['packed', 'cancelled'],
        'packed': ['shipped', 'cancelled'],
        'shipped': ['completed', 'cancelled'],
        'completed': ['returned'],
        'cancelled': [],
        'returned': [],
    }

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sales')
    reference = models.CharField(max_length=50)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='sales')
    date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='cod')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UZS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sales_created')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        customer_name = self.customer.name if self.customer else 'Walk-in'
        return f"{self.reference} - {customer_name}"

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
    def total_reserved(self):
        return sum(item.reserved_quantity for item in self.items.all())

    @property
    def total_picked(self):
        return sum(item.picked_quantity for item in self.items.all())

    @property
    def total_shipped(self):
        return sum(item.shipped_quantity for item in self.items.all())

    @property
    def total_returned(self):
        return sum(item.returned_quantity for item in self.items.all())

    @property
    def total_paid_amount(self):
        return self.payments.aggregate(t=models.Sum('amount'))['t'] or 0

    @property
    def outstanding_balance(self):
        return self.total - self.total_paid_amount

    @property
    def reservation_status(self):
        if self.total_reserved == 0:
            return 'not_reserved'
        if self.total_reserved >= self.total_ordered:
            return 'fully_reserved'
        return 'partially_reserved'


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    reserved_quantity = models.PositiveIntegerField(default=0)
    picked_quantity = models.PositiveIntegerField(default=0)
    shipped_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)
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
        return self.quantity - self.shipped_quantity

    @property
    def available_to_reserve(self):
        return self.quantity - self.reserved_quantity

    @property
    def is_fully_shipped(self):
        return self.shipped_quantity >= self.quantity


class SaleReturn(models.Model):
    REASON_CHOICES = [
        ('damaged', 'Damaged'),
        ('wrong_product', 'Wrong Product'),
        ('defective', 'Defective'),
        ('changed_mind', 'Customer Changed Mind'),
        ('other', 'Other'),
    ]
    CONDITION_CHOICES = [
        ('sellable', 'Sellable'),
        ('damaged', 'Damaged'),
        ('quarantine', 'Quarantine'),
        ('inspection', 'Needs Inspection'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sale_returns')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='returns')
    reference = models.CharField(max_length=50)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reason_notes = models.TextField(blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='sellable')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return {self.reference} - {self.sale.reference}"

    def calculate_total(self):
        total = sum(item.quantity * item.unit_price for item in self.items.all())
        self.total = total
        self.save(update_fields=['total', 'updated_at'])


class SaleReturnItem(models.Model):
    return_order = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name='items')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class SalePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
        ('online', 'Online'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sale_payments')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sale.reference} - {self.amount} {self.sale.currency}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total_paid = SalePayment.objects.filter(sale=self.sale).aggregate(
            t=models.Sum('amount')
        )['t'] or 0
        if total_paid >= self.sale.total:
            self.sale.payment_status = 'paid'
        elif total_paid > 0:
            self.sale.payment_status = 'partial'
        else:
            self.sale.payment_status = 'unpaid'
        self.sale.save(update_fields=['payment_status', 'updated_at'])


class Debt(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pos_debts')
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='debt')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='pos_debts')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pos_debts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-created_at']
        indexes = [models.Index(fields=['company', 'status']), models.Index(fields=['customer', 'due_date'])]

    @property
    def remaining(self):
        return max(self.total - self.paid, 0)

    def refresh_status(self, save=True):
        if self.remaining <= 0:
            self.status = 'paid'
        elif self.due_date < timezone.localdate():
            self.status = 'overdue'
        elif self.paid > 0:
            self.status = 'partial'
        else:
            self.status = 'open'
        if save:
            self.save(update_fields=['status', 'updated_at'])
        return self.status


class DebtPayment(models.Model):
    PAYMENT_METHOD_CHOICES = SalePayment.PAYMENT_METHOD_CHOICES

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pos_debt_payments')
    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    date = models.DateField(default=timezone.localdate)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pos_debt_payments')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
