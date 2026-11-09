from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import uuid
from users.models import Company


class SalesChannel(models.Model):
    CHANNEL_TYPE_CHOICES = [
        ('pos', 'POS / Physical Store'),
        ('website', 'Online Store / Website'),
        ('telegram', 'Telegram Commerce'),
        ('marketplace', 'Marketplace'),
        ('manual', 'Sales Manager / Manual'),
        ('mobile', 'Mobile App'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('setup', 'Setup Required'),
        ('error', 'Error'),
    ]
    CURRENCY_CHOICES = [
        ('UZS', 'UZS'), ('USD', 'USD'), ('EUR', 'EUR'), ('RUB', 'RUB'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sales_channels')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    is_default = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UZS')
    price_list = models.ForeignKey(
        'pricing.PriceList', on_delete=models.SET_NULL, null=True, blank=True, related_name='channels'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name='channels'
    )
    website_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    settings_json = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, choices=[
        ('synced', 'Synced'), ('pending', 'Pending'),
        ('error', 'Error'), ('never', 'Never Synced'),
    ], default='never')
    orders_today = models.PositiveIntegerField(default=0)
    revenue_today = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'code']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['channel_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name).replace('-', '_')[:50]
        super().save(*args, **kwargs)

    @property
    def total_orders(self):
        return self.channel_orders.count()

    @property
    def total_revenue(self):
        return self.channel_orders.filter(
            status__in=['completed', 'delivered', 'shipped']
        ).aggregate(t=models.Sum('total'))['t'] or 0


class ChannelProduct(models.Model):
    VISIBILITY_CHOICES = [
        ('visible', 'Visible'),
        ('hidden', 'Hidden'),
        ('draft', 'Draft'),
        ('out_of_stock', 'Out of Stock'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='channel_products')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='channel_products')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='visible')
    channel_title = models.CharField(max_length=300, blank=True)
    channel_description = models.TextField(blank=True)
    channel_image = models.ImageField(upload_to='channel_products/', blank=True, null=True)
    channel_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Override price for this channel. Leave empty to use price list.'
    )
    channel_category = models.CharField(max_length=200, blank=True)
    channel_sort_order = models.IntegerField(default=0)
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    slug = models.SlugField(max_length=300, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['channel', 'product']
        ordering = ['channel_sort_order', 'product__name']
        indexes = [
            models.Index(fields=['channel', 'visibility']),
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.product.name} on {self.channel.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.channel_title or self.product.name)
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        return self.channel_title or self.product.name

    @property
    def display_description(self):
        return self.channel_description or self.product.description or ''

    @property
    def display_price(self):
        if self.channel_price:
            return self.channel_price
        return self.product.price

    @property
    def display_image(self):
        if self.channel_image:
            return self.channel_image
        return self.product.image


class ChannelCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='channel_categories')
    category = models.ForeignKey('products.Category', on_delete=models.CASCADE, related_name='channel_mappings')
    channel_name = models.CharField(max_length=200)
    channel_slug = models.SlugField(max_length=200, blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['channel', 'category']
        ordering = ['sort_order', 'channel_name']

    def __str__(self):
        return f"{self.category.name} -> {self.channel_name}"

    def save(self, *args, **kwargs):
        if not self.channel_slug:
            self.channel_slug = slugify(self.channel_name)
        super().save(*args, **kwargs)


class ChannelStockAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='stock_allocations')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='channel_allocations')
    allocated_quantity = models.PositiveIntegerField(default=0)
    safety_stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['channel', 'product']

    def __str__(self):
        return f"{self.product.name} -> {self.channel.name}: {self.allocated_quantity}"

    @property
    def available_for_channel(self):
        product_stock = self.product.quantity
        return max(0, min(self.allocated_quantity, product_stock) - self.safety_stock)


class PaymentProvider(models.Model):
    PROVIDER_TYPE_CHOICES = [
        ('payme', 'Payme'),
        ('click', 'Click'),
        ('stripe', 'Stripe'),
        ('uzum', 'Uzum Bank'),
        ('bank_transfer', 'Bank Transfer'),
        ('cod', 'Cash on Delivery'),
        ('manual', 'Manual'),
        ('custom', 'Custom'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_providers')
    name = models.CharField(max_length=200)
    provider_type = models.CharField(max_length=30, choices=PROVIDER_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    is_default = models.BooleanField(default=False)
    config_json = models.JSONField(default=dict, blank=True)
    merchant_id = models.CharField(max_length=200, blank=True)
    api_url = models.URLField(blank=True)
    redirect_url = models.URLField(blank=True)
    webhook_url = models.URLField(blank=True)
    test_mode = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_transactions')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions')
    channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    provider = models.ForeignKey(PaymentProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_id = models.CharField(max_length=200, blank=True)
    external_id = models.CharField(max_length=200, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='UZS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    response_json = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=200, blank=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['external_id']),
            models.Index(fields=['status']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:16].upper()}"
        if not self.idempotency_key:
            self.idempotency_key = f"pay_{uuid.uuid4().hex}"
        super().save(*args, **kwargs)


class MarketplaceIntegration(models.Model):
    MARKETPLACE_CHOICES = [
        ('uzum', 'Uzum'),
        ('wildberries', 'Wildberries'),
        ('ozon', 'Ozon'),
        ('amazon', 'Amazon'),
        ('ebay', 'eBay'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Connected'),
        ('inactive', 'Not Connected'),
        ('error', 'Error'),
        ('setup', 'Setup Required'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='marketplace_integrations')
    channel = models.OneToOneField(SalesChannel, on_delete=models.CASCADE, related_name='marketplace_config', null=True, blank=True)
    name = models.CharField(max_length=200)
    marketplace_type = models.CharField(max_length=30, choices=MARKETPLACE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    config_json = models.JSONField(default=dict, blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    shop_id = models.CharField(max_length=200, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    total_products_synced = models.PositiveIntegerField(default=0)
    total_orders_imported = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_marketplace_type_display()})"


class MarketplaceProductMapping(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
        ('pending', 'Pending Sync'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(MarketplaceIntegration, on_delete=models.CASCADE, related_name='product_mappings')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='marketplace_mappings')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE, null=True, blank=True, related_name='marketplace_mappings')
    external_product_id = models.CharField(max_length=200, blank=True)
    external_sku = models.CharField(max_length=200, blank=True)
    external_category = models.CharField(max_length=300, blank=True)
    external_status = models.CharField(max_length=50, blank=True)
    sync_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    internal_stock = models.PositiveIntegerField(default=0)
    external_stock = models.PositiveIntegerField(default=0)
    last_stock_sync = models.DateTimeField(null=True, blank=True)
    internal_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    external_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_price_sync = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'product', 'variant']
        ordering = ['product__name']

    def __str__(self):
        return f"{self.product.name} <-> {self.integration.name}"


class IntegrationLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='integration_logs')
    provider = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='info')
    external_id = models.CharField(max_length=200, blank=True)
    request_summary = models.TextField(blank=True)
    response_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'provider']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"[{self.provider}] {self.action} - {self.get_status_display()}"


class SyncJob(models.Model):
    JOB_TYPE_CHOICES = [
        ('product_sync', 'Product Sync'),
        ('price_sync', 'Price Sync'),
        ('stock_sync', 'Stock Sync'),
        ('order_import', 'Order Import'),
        ('order_status', 'Order Status Update'),
        ('full_sync', 'Full Sync'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sync_jobs')
    integration = models.ForeignKey(MarketplaceIntegration, on_delete=models.CASCADE, related_name='sync_jobs', null=True, blank=True)
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='sync_jobs', null=True, blank=True)
    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_items = models.PositiveIntegerField(default=0)
    processed_items = models.PositiveIntegerField(default=0)
    failed_items = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['job_type']),
        ]

    def __str__(self):
        return f"{self.get_job_type_display()} - {self.get_status_display()}"

    @property
    def progress_percentage(self):
        if self.total_items == 0:
            return 0
        return round((self.processed_items / self.total_items) * 100, 1)

    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status == 'failed'


class WebhookConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='webhook_configs')
    name = models.CharField(max_length=200)
    url = models.URLField()
    secret = models.CharField(max_length=500, blank=True)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    failure_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} -> {self.url}"


class ShippingMethod(models.Model):
    CALCULATION_CHOICES = [
        ('fixed', 'Fixed Fee'),
        ('free', 'Free Shipping'),
        ('weight', 'Weight Based'),
        ('distance', 'Distance Based'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shipping_methods')
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='shipping_methods', null=True, blank=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    calculation = models.CharField(max_length=20, choices=CALCULATION_CHOICES, default='fixed')
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_kg_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_days_min = models.PositiveIntegerField(default=1)
    estimated_days_max = models.PositiveIntegerField(default=7)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_calculation_display()})"

    def calculate_fee(self, subtotal=0, weight=0):
        if self.calculation == 'free':
            return Decimal('0')
        if self.free_threshold and subtotal >= self.free_threshold:
            return Decimal('0')
        fee = self.base_fee
        if self.calculation == 'weight':
            fee += self.per_kg_fee * Decimal(str(weight))
        return fee.quantize(Decimal('0.01'))


class ChannelOrderMixin:
    pass
