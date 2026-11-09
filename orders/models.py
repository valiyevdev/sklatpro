from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from users.models import Company


class Order(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('on_hold', 'On Hold'),
        ('reserved', 'Reserved'),
        ('processing', 'Processing'),
        ('picking', 'Picking'),
        ('partially_picked', 'Partially Picked'),
        ('picked', 'Picked'),
        ('packing', 'Packing'),
        ('packed', 'Packed'),
        ('ready_to_ship', 'Ready to Ship'),
        ('shipped', 'Shipped'),
        ('partially_fulfilled', 'Partially Fulfilled'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('backordered', 'Backordered'),
        ('returned', 'Returned'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    PAYMENT_TERMS_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('prepaid', 'Prepaid'),
        ('net7', 'Net 7'),
        ('net15', 'Net 15'),
        ('net30', 'Net 30'),
        ('credit', 'Credit'),
    ]

    VALID_TRANSITIONS = {
        'draft': ['pending', 'confirmed', 'cancelled'],
        'pending': ['confirmed', 'on_hold', 'cancelled'],
        'confirmed': ['reserved', 'processing', 'on_hold', 'cancelled'],
        'on_hold': ['confirmed', 'cancelled'],
        'reserved': ['processing', 'picking', 'cancelled'],
        'processing': ['picking', 'cancelled'],
        'picking': ['partially_picked', 'picked', 'cancelled'],
        'partially_picked': ['picked', 'picking', 'cancelled'],
        'picked': ['packing', 'cancelled'],
        'packing': ['packed', 'cancelled'],
        'packed': ['ready_to_ship', 'cancelled'],
        'ready_to_ship': ['shipped', 'cancelled'],
        'shipped': ['delivered', 'partially_fulfilled', 'cancelled'],
        'partially_fulfilled': ['shipped', 'delivered', 'cancelled'],
        'delivered': ['completed', 'returned'],
        'completed': ['returned'],
        'cancelled': [],
        'backordered': ['reserved', 'processing', 'cancelled'],
        'returned': [],
    }

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='orders')
    reference = models.CharField(max_length=50)
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='orders')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, related_name='orders')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='cod')
    currency = models.CharField(max_length=3, default='UZS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    delivery_address = models.TextField(blank=True)
    delivery_phone = models.CharField(max_length=20, blank=True)
    delivery_method = models.CharField(max_length=50, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='orders_created')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['customer']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.customer.name}"

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
    def total_requested(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_reserved(self):
        return sum(item.reserved_quantity for item in self.items.all())

    @property
    def total_picked(self):
        return sum(item.picked_quantity for item in self.items.all())

    @property
    def total_packed(self):
        return sum(item.packed_quantity for item in self.items.all())

    @property
    def total_shipped(self):
        return sum(item.shipped_quantity for item in self.items.all())

    @property
    def total_delivered(self):
        return sum(item.delivered_quantity for item in self.items.all())

    @property
    def total_returned(self):
        return sum(item.returned_quantity for item in self.items.all())

    @property
    def total_backordered(self):
        return sum(item.backordered_quantity for item in self.items.all())

    @property
    def total_paid_amount(self):
        return self.payments.aggregate(t=models.Sum('amount'))['t'] or 0

    @property
    def outstanding_balance(self):
        return self.total - self.total_paid_amount

    @property
    def fulfillment_percentage(self):
        if self.total_requested == 0:
            return 0
        return round((self.total_delivered / self.total_requested) * 100, 1)

    @property
    def reservation_status(self):
        if self.total_reserved == 0:
            return 'not_reserved'
        if self.total_reserved >= self.total_requested:
            return 'fully_reserved'
        return 'partially_reserved'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField()
    reserved_quantity = models.PositiveIntegerField(default=0)
    picked_quantity = models.PositiveIntegerField(default=0)
    packed_quantity = models.PositiveIntegerField(default=0)
    shipped_quantity = models.PositiveIntegerField(default=0)
    delivered_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)
    backordered_quantity = models.PositiveIntegerField(default=0)
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
    def remaining_to_pick(self):
        return self.quantity - self.picked_quantity

    @property
    def remaining_to_ship(self):
        return self.picked_quantity - self.shipped_quantity

    @property
    def remaining_to_deliver(self):
        return self.shipped_quantity - self.delivered_quantity

    @property
    def is_fully_delivered(self):
        return self.delivered_quantity >= self.quantity


class OrderPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
        ('online', 'Online'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='order_payments')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.reference} - {self.amount}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total_paid = OrderPayment.objects.filter(order=self.order).aggregate(
            t=models.Sum('amount')
        )['t'] or 0
        if total_paid >= self.order.total:
            self.order.payment_status = 'paid'
        elif total_paid > 0:
            self.order.payment_status = 'partial'
        else:
            self.order.payment_status = 'unpaid'
        self.order.save(update_fields=['payment_status', 'updated_at'])
