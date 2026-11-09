from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
import uuid
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files import File
import qrcode
from users.models import Company


class Category(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Brand(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='brands', null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        indexes = [
            models.Index(fields=['company']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Unit(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, blank=True)
    base_unit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='derived_units')
    conversion_factor = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'

    def __str__(self):
        if self.symbol:
            return f'{self.name} ({self.symbol})'
        return self.name


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('electronics', 'Elektronika'),
        ('clothing', 'Kiyimlar'),
        ('food', 'Oziq-ovqat'),
        ('furniture', 'Mebel'),
        ('tools', 'Asboblar'),
        ('other', 'Boshqa'),
    ]

    PRODUCT_TYPE_CHOICES = [
        ('food', 'Oziq-ovqat'),
        ('sweets', 'Shirinlik'),
        ('material', 'Material / Qurilish'),
        ('general', 'Standart / Boshqa'),
    ]

    WEIGHT_UNIT_CHOICES = [
        ('g', 'Gramm (g)'),
        ('kg', 'Kilogramm (kg)'),
    ]

    NETTO_BRUTTO_CHOICES = [
        ('netto', 'Netto'),
        ('brutto', 'Brutto'),
    ]

    MEASUREMENT_UNIT_CHOICES = [
        ('m2', 'm²'),
        ('m', 'Metr'),
        ('dona', 'Dona'),
        ('kg', 'kg'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_products', null=True, blank=True, verbose_name="Company")
    name = models.CharField(max_length=200, verbose_name="Product Name")
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other', verbose_name="Category")
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='general', verbose_name="Product Type")
    storage_conditions = models.CharField(max_length=200, blank=True, null=True, verbose_name="Storage Conditions")
    weight_unit = models.CharField(max_length=10, choices=WEIGHT_UNIT_CHOICES, default='kg', blank=True, verbose_name="Weight Unit")
    netto_brutto = models.CharField(max_length=10, choices=NETTO_BRUTTO_CHOICES, blank=True, null=True, verbose_name="Netto / Brutto")
    measurement_unit = models.CharField(max_length=10, choices=MEASUREMENT_UNIT_CHOICES, blank=True, null=True, verbose_name="Measurement Unit")
    volume = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Volume (m³)")
    category_fk = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Category (detailed)")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Brand")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Unit")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Quantity")
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Sale Price")
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Wholesale Price")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Purchase Price")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    supplier = models.CharField(max_length=200, blank=True, null=True, verbose_name="Supplier")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Product Image")
    slug = models.SlugField(max_length=250, blank=True, verbose_name="Slug")
    barcode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Barcode")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name="QR Code")
    batch_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Batch Number")
    expiration_date = models.DateField(blank=True, null=True, verbose_name="Expiration Date")
    shelf = models.CharField(max_length=50, blank=True, null=True, verbose_name="Shelf")
    rack = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rack")
    section = models.CharField(max_length=50, blank=True, null=True, verbose_name="Section")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    min_stock = models.PositiveIntegerField(default=5, verbose_name="Minimum Stock")
    max_stock = models.PositiveIntegerField(default=1000, verbose_name="Maximum Stock")
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Weight (kg)")
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Length (cm)")
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Width (cm)")
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Height (cm)")
    notes = models.TextField(blank=True, verbose_name="Internal Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
            models.Index(fields=['quantity']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['barcode']),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.sku:
            base_sku = slugify(self.name).replace('-', '').upper()[:8]
            random_num = str(uuid.uuid4().int)[:4]
            self.sku = f"{base_sku}{random_num}"
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.barcode:
            self.barcode = self.sku
        self.generate_qr_code()
        super().save(*args, **kwargs)

    def generate_qr_code(self):
        if not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(f"Product: {self.name}\nSKU: {self.sku}\nPrice: {self.price}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            filename = f"qr_{self.sku}.png"
            self.qr_code.save(filename, File(buffer), save=False)

    def generate_barcode_image(self):
        if self.barcode:
            code128 = barcode.get_barcode_class('code128')
            barcode_instance = code128(self.barcode, writer=ImageWriter())
            buffer = BytesIO()
            barcode_instance.write(buffer)
            buffer.seek(0)
            return buffer
        return None

    @property
    def available_stock(self):
        return self.quantity

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock

    # ------------------------------------------------------------
    # Canonical stock-bucket querysets.
    #
    # `stock_status` above is the single source of truth for what a
    # product's state is, but it cannot be used in a filter() call. These
    # classmethods mirror it exactly so every surface that counts or lists
    # a bucket (dashboard alert tabs, the three list views, reports) agrees
    # with the per-product status. Previously each of those places inlined
    # its own `quantity__lte` / `quantity__gte` filter and they drifted:
    # overstock did not exclude the low/out-of-stock ranges, so a product
    # whose min_stock was >= its max_stock was counted as BOTH low_stock
    # and overstock and the tab totals exceeded the real product count.
    #
    # Note the ordering in `stock_status` is out_of_stock -> low_stock ->
    # overstock, so each later bucket must exclude the earlier ranges.
    # `quantity__lte=0` was also used for out-of-stock, which differs from
    # `quantity == 0` if a negative quantity is ever stored.
    # ------------------------------------------------------------

    @classmethod
    def _scoped(cls, queryset, company):
        return queryset.filter(company=company) if company is not None else queryset

    # Field lookups per bucket, usable against any pre-scoped queryset via
    # `base.filter(**Product.STOCK_BUCKET_FILTERS[status])`.
    STOCK_BUCKET_FILTERS = {
        'out_of_stock': {'quantity': 0},
        'low_stock': {'quantity__gt': 0, 'quantity__lte': models.F('min_stock')},
        'overstock': {
            'quantity__gt': models.F('min_stock'),
            'quantity__gte': models.F('max_stock'),
        },
        'in_stock': {
            'quantity__gt': models.F('min_stock'),
            'quantity__lt': models.F('max_stock'),
        },
    }

    @classmethod
    def low_stock_qs(cls, company=None):
        """quantity > 0 and quantity <= min_stock."""
        return cls._scoped(
            cls.objects.filter(**cls.STOCK_BUCKET_FILTERS['low_stock']),
            company,
        )

    @classmethod
    def out_of_stock_qs(cls, company=None):
        """quantity == 0 (evaluated first by stock_status)."""
        return cls._scoped(
            cls.objects.filter(**cls.STOCK_BUCKET_FILTERS['out_of_stock']),
            company,
        )

    @classmethod
    def overstock_qs(cls, company=None):
        """quantity > min_stock and quantity >= max_stock.

        The `quantity__gt=min_stock` term is what stops this bucket from
        swallowing products that stock_status classifies as low_stock.
        """
        return cls._scoped(
            cls.objects.filter(**cls.STOCK_BUCKET_FILTERS['overstock']),
            company,
        )

    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity <= self.min_stock:
            return 'low_stock'
        elif self.quantity >= self.max_stock:
            return 'overstock'
        else:
            return 'in_stock'

    @property
    def stock_status_display(self):
        status_map = {
            'out_of_stock': 'Tugagan',
            'low_stock': 'Kam qolgan',
            'overstock': "Oshib ketgan",
            'in_stock': 'Bor'
        }
        return status_map.get(self.stock_status, "Noma'lum")

    @property
    def stock_status_color(self):
        color_map = {
            'out_of_stock': 'danger',
            'low_stock': 'warning',
            'overstock': 'info',
            'in_stock': 'success'
        }
        return color_map.get(self.stock_status, 'secondary')

    @property
    def is_expired(self):
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False

    @property
    def is_expiring_soon(self):
        if self.expiration_date and not self.is_expired:
            days_until_expiry = (self.expiration_date - timezone.now().date()).days
            return days_until_expiry <= 30
        return False

    @property
    def expiration_status(self):
        if not self.expiration_date:
            return 'none'
        elif self.is_expired:
            return 'expired'
        elif self.is_expiring_soon:
            return 'expiring_soon'
        else:
            return 'good'

    @property
    def expiration_status_display(self):
        status_map = {
            'none': 'Belgilanmagan',
            'expired': "Muddati o'tgan",
            'expiring_soon': 'Tez orada tugaydi',
            'good': 'Yaxshi'
        }
        return status_map.get(self.expiration_status, "Noma'lum")

    @property
    def expiration_status_color(self):
        color_map = {
            'none': 'secondary',
            'expired': 'danger',
            'expiring_soon': 'warning',
            'good': 'success'
        }
        return color_map.get(self.expiration_status, 'secondary')

    @property
    def inventory_value(self):
        return self.quantity * self.price

    @property
    def profit_margin(self):
        if self.purchase_price and self.purchase_price > 0:
            return ((self.price - self.purchase_price) / self.purchase_price) * 100
        return 0

    @property
    def has_variants(self):
        return self.variants.exists()


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=200, verbose_name="Variant Name")
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    barcode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Barcode")
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Sale Price")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Purchase Price")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Quantity")
    image = models.ImageField(upload_to='products/variants/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.sku:
            base = slugify(f"{self.product.sku}-{self.name}").replace('-', '').upper()[:12]
            random_num = str(uuid.uuid4().int)[:4]
            self.sku = f"{base}{random_num}"
        if not self.barcode:
            self.barcode = self.sku
        super().save(*args, **kwargs)

    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity < 5:
            return 'low_stock'
        else:
            return 'in_stock'
