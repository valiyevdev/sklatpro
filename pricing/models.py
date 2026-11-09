from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from users.models import Company


class PriceList(models.Model):
    CURRENCY_CHOICES = [
        ('UZS', 'UZS'), ('USD', 'USD'), ('EUR', 'EUR'), ('RUB', 'RUB'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'), ('inactive', 'Inactive'), ('scheduled', 'Scheduled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='price_lists')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UZS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    customer_segment = models.ForeignKey(
        'crm.CustomerSegment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='price_lists'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='price_lists'
    )
    channel = models.CharField(max_length=30, blank=True, choices=[
        ('', 'All'), ('retail', 'Retail'), ('pos', 'POS'), ('website', 'Website'),
        ('telegram', 'Telegram'), ('marketplace', 'Marketplace'), ('wholesale', 'Wholesale'),
        ('sales_manager', 'Sales Manager'),
    ])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']
        unique_together = ['company', 'code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_currently_valid(self):
        now = timezone.now().date()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return self.status == 'active'

    @property
    def entry_count(self):
        return self.entries.count()


class PriceListEntry(models.Model):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='entries')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='price_entries')
    variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE, null=True, blank=True,
        related_name='price_entries'
    )
    price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['product', 'min_quantity']
        unique_together = ['price_list', 'product', 'variant', 'min_quantity']

    def __str__(self):
        return f"{self.product.name} @ {self.price} ({self.price_list.code})"

    @property
    def is_currently_valid(self):
        now = timezone.now().date()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return self.is_active


class CustomerSpecificPrice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_prices')
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='specific_prices')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='customer_prices')
    variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE, null=True, blank=True,
        related_name='customer_prices'
    )
    price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='UZS')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'price']
        unique_together = ['company', 'customer', 'product', 'variant', 'min_quantity']

    def __str__(self):
        return f"{self.customer.name} → {self.product.name} @ {self.price}"

    @property
    def is_currently_valid(self):
        now = timezone.now().date()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return self.is_active


class Promotion(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'), ('fixed', 'Fixed Amount'),
        ('fixed_price', 'Fixed Price'), ('bogo', 'Buy X Get Y'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'), ('inactive', 'Inactive'), ('scheduled', 'Scheduled'),
    ]
    COMBINE_CHOICES = [
        ('none', 'No Stacking'), ('price_list', 'With Price List'),
        ('coupon', 'With Coupon'), ('all', 'Stack All'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='promotions')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    free_product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bogo_promotions'
    )
    free_quantity = models.PositiveIntegerField(default=1)
    buy_quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.PositiveIntegerField(default=0)
    combine_with = models.CharField(max_length=20, choices=COMBINE_CHOICES, default='none')
    max_total_uses = models.PositiveIntegerField(null=True, blank=True)
    max_per_customer = models.PositiveIntegerField(null=True, blank=True)
    current_uses = models.PositiveIntegerField(default=0)
    min_order_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    min_quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    applicable_products = models.ManyToManyField('products.Product', blank=True, related_name='promotions')
    applicable_categories = models.ManyToManyField('products.Category', blank=True, related_name='promotions')
    applicable_customers = models.ManyToManyField('sales.Customer', blank=True, related_name='promotions')
    applicable_segments = models.ManyToManyField(
        'crm.CustomerSegment', blank=True, related_name='promotions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

    @property
    def is_currently_valid(self):
        now = timezone.now()
        today = now.date()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        if self.start_time and now.time() < self.start_time:
            return False
        if self.end_time and now.time() > self.end_time:
            return False
        if self.max_total_uses and self.current_uses >= self.max_total_uses:
            return False
        return self.status == 'active'

    def calculate_discount(self, amount):
        if self.discount_type == 'percentage':
            return (amount * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        elif self.discount_type == 'fixed':
            return min(self.discount_value, amount)
        elif self.discount_type == 'fixed_price':
            return max(amount - self.discount_value, Decimal('0'))
        return Decimal('0')


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'), ('fixed', 'Fixed Amount'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='coupons')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    max_total_uses = models.PositiveIntegerField(null=True, blank=True)
    max_per_customer = models.PositiveIntegerField(default=1)
    min_order_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_uses = models.PositiveIntegerField(default=0)
    applicable_products = models.ManyToManyField('products.Product', blank=True, related_name='coupons')
    applicable_categories = models.ManyToManyField('products.Category', blank=True, related_name='coupons')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'code']

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()}: {self.discount_value})"

    @property
    def is_currently_valid(self):
        today = timezone.now().date()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        if self.max_total_uses and self.current_uses >= self.max_total_uses:
            return False
        return self.is_active

    def calculate_discount(self, amount):
        if self.discount_type == 'percentage':
            disc = (amount * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
            if self.max_discount_amount:
                disc = min(disc, self.max_discount_amount)
            return min(disc, amount)
        return min(self.discount_value, amount)


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} used by {self.customer}"


class PriceHistory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='price_history')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='price_history')
    variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE, null=True, blank=True,
        related_name='price_history'
    )
    price_list = models.ForeignKey(
        PriceList, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='history'
    )
    old_price = models.DecimalField(max_digits=14, decimal_places=2)
    new_price = models.DecimalField(max_digits=14, decimal_places=2)
    change_type = models.CharField(max_length=30, choices=[
        ('product_base', 'Product Base Price'),
        ('price_list', 'Price List Entry'),
        ('customer_price', 'Customer Specific Price'),
        ('promotion', 'Promotion'),
        ('coupon', 'Coupon'),
    ])
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.product.name}: {self.old_price} → {self.new_price}"
