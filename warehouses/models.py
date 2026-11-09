from django.db import models
from django.conf import settings
from django.utils import timezone
from users.models import Company


class Warehouse(models.Model):
    WAREHOUSE_TYPES = [
        ('main', 'Main Warehouse'),
        ('distribution', 'Distribution Center'),
        ('retail', 'Retail Store'),
        ('cold_storage', 'Cold Storage'),
        ('temporary', 'Temporary Warehouse'),
        ('virtual', 'Virtual Warehouse'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='warehouses')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_warehouses')
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='main')
    is_active = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False)
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Total capacity in units')
    working_hours = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'code']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_locations(self):
        return self.locations.count()

    @property
    def active_zones(self):
        return self.zones.filter(is_active=True).count()


class Zone(models.Model):
    LOCATION_TYPES = [
        ('receiving', 'Receiving'),
        ('storage', 'Storage'),
        ('picking', 'Picking'),
        ('packing', 'Packing'),
        ('shipping', 'Shipping'),
        ('returns', 'Returns'),
        ('damaged', 'Damaged'),
        ('cold_storage', 'Cold Storage'),
        ('high_value', 'High Value'),
        ('quarantine', 'Quarantine'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='zones')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    zone_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='storage')
    description = models.TextField(blank=True, default='')
    temperature_controlled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        unique_together = ['warehouse', 'code']
        indexes = [
            models.Index(fields=['warehouse']),
            models.Index(fields=['company']),
        ]

    def __str__(self):
        return f"{self.warehouse.code}-{self.code}"


class Location(models.Model):
    LOCATION_TYPES = [
        ('receiving', 'Receiving'),
        ('storage', 'Storage'),
        ('picking', 'Picking'),
        ('packing', 'Packing'),
        ('shipping', 'Shipping'),
        ('returns', 'Returns'),
        ('damaged', 'Damaged'),
        ('quarantine', 'Quarantine'),
        ('virtual', 'Virtual'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('full', 'Full'),
        ('locked', 'Locked'),
        ('inactive', 'Inactive'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='locations')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='locations')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='locations')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='storage')
    rack = models.CharField(max_length=10, blank=True, default='')
    shelf = models.CharField(max_length=10, blank=True, default='')
    bin_code = models.CharField(max_length=10, blank=True, default='')
    aisle = models.CharField(max_length=10, blank=True, default='')
    capacity_qty = models.PositiveIntegerField(null=True, blank=True)
    capacity_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    capacity_volume = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    barcode = models.CharField(max_length=100, blank=True, default='')
    qr_code = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        unique_together = ['warehouse', 'code']
        indexes = [
            models.Index(fields=['warehouse']),
            models.Index(fields=['zone']),
            models.Index(fields=['company']),
            models.Index(fields=['barcode']),
        ]

    def __str__(self):
        parts = [self.warehouse.code]
        if self.zone:
            parts.append(self.zone.code)
        if self.rack:
            parts.append(f"R{self.rack}")
        if self.shelf:
            parts.append(f"S{self.shelf}")
        if self.bin_code:
            parts.append(f"B{self.bin_code}")
        return "-".join(parts) if len(parts) > 1 else self.code

    @property
    def full_code(self):
        return str(self)


class Batch(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('quarantine', 'Quarantine'),
        ('consumed', 'Consumed'),
        ('damaged', 'Damaged'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='batches')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=100)
    supplier = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='batches')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='batches')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='batches')
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    receipt_date = models.DateField()
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date', '-created_at']
        unique_together = ['company', 'product', 'batch_number', 'warehouse']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['batch_number']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f"{self.product.name} | {self.batch_number}"

    @property
    def available_quantity(self):
        return self.quantity - self.reserved_quantity

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False

    @property
    def is_expiring_soon(self, days=30):
        if self.expiry_date:
            return self.expiry_date <= timezone.now().date() + timezone.timedelta(days=days)
        return False


class SerialNumber(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('damaged', 'Damaged'),
        ('returned', 'Returned'),
        ('quarantine', 'Quarantine'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='serial_numbers')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='serial_numbers')
    serial = models.CharField(max_length=100)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='serial_numbers')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='serial_numbers')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='serial_numbers')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='serial_numbers')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='serial_numbers')
    transfer = models.ForeignKey('Transfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='serial_numbers')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['serial']
        unique_together = ['company', 'product', 'serial']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['serial']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.product.name} | {self.serial}"


class StockLocation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_locations')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='stock_locations')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_locations')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='stock_levels')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_locations')
    quantity = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['location', 'product']
        unique_together = ['company', 'product', 'warehouse', 'location', 'batch']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.location} ({self.quantity})"

    @property
    def available(self):
        return self.quantity - self.reserved


# ─── OPERATIONS ───


class Receiving(models.Model):
    STATUS_CHOICES = [
        ('expected', 'Expected'),
        ('arrived', 'Arrived'),
        ('unloading', 'Unloading'),
        ('inspection', 'Inspection'),
        ('accepted', 'Accepted'),
        ('putaway', 'Put-away'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('partial', 'Partial'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='receiving_orders')
    reference = models.CharField(max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='receiving_orders')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='receiving_orders')
    supplier = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='receiving_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='expected')
    expected_date = models.DateField(null=True, blank=True)
    actual_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='receiving_tasks')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_receiving')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['warehouse']),
        ]

    def __str__(self):
        return f"{self.reference}"

    @property
    def total_expected(self):
        return sum(item.expected_quantity for item in self.items.all())

    @property
    def total_received(self):
        return sum(item.received_quantity for item in self.items.all())

    @property
    def total_damaged(self):
        return sum(item.damaged_quantity for item in self.items.all())

    @property
    def total_rejected(self):
        return sum(item.rejected_quantity for item in self.items.all())

    @property
    def progress_percent(self):
        expected = self.total_expected
        if expected == 0:
            return 0
        return min(100, round(self.total_received / expected * 100))


class ReceivingItem(models.Model):
    receiving = models.ForeignKey(Receiving, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    expected_quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True, default='')
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['product__name']

    def __str__(self):
        return f"{self.product.name}: {self.received_quantity}/{self.expected_quantity}"

    @property
    def remaining_quantity(self):
        return max(0, self.expected_quantity - self.received_quantity - self.damaged_quantity - self.rejected_quantity)

    @property
    def is_complete(self):
        return self.remaining_quantity <= 0


class PutAway(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='putaway_tasks')
    reference = models.CharField(max_length=50)
    receiving = models.ForeignKey(Receiving, on_delete=models.SET_NULL, null=True, blank=True, related_name='putaway_tasks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='putaway_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='putaway_assignments')
    notes = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['warehouse']),
        ]

    def __str__(self):
        return self.reference

    @property
    def total_items(self):
        return self.items.count()

    @property
    def completed_items(self):
        return self.items.filter(is_putaway=True).count()


class PutAwayItem(models.Model):
    putaway = models.ForeignKey(PutAway, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='putaway_from')
    to_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='putaway_to')
    is_putaway = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.product.name} → {self.to_location}"


class PickingList(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('picked', 'Picked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STRATEGY_CHOICES = [
        ('single', 'Single Order'),
        ('batch', 'Batch'),
        ('wave', 'Wave'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='picking_lists')
    reference = models.CharField(max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='picking_lists')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='picking_lists')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    strategy = models.CharField(max_length=10, choices=STRATEGY_CHOICES, default='single')
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='picking_assignments')
    notes = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['warehouse']),
        ]

    def __str__(self):
        return self.reference

    @property
    def total_items(self):
        return self.items.count()

    @property
    def picked_items(self):
        return self.items.filter(is_picked=True).count()

    @property
    def progress_percent(self):
        total = self.total_items
        if total == 0:
            return 0
        return min(100, round(self.picked_items / total * 100))


class PickingItem(models.Model):
    picking_list = models.ForeignKey(PickingList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    picked_quantity = models.PositiveIntegerField(default=0)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    is_picked = models.BooleanField(default=False)
    is_short_pick = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['location__code', 'product__name']

    def __str__(self):
        return f"{self.product.name}: {self.picked_quantity}/{self.quantity}"


class PackingList(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('packed', 'Packed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='packing_lists')
    reference = models.CharField(max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='packing_lists')
    picking_list = models.ForeignKey(PickingList, on_delete=models.SET_NULL, null=True, blank=True, related_name='packing_lists')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='packing_lists')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    packer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='packing_assignments')
    package_count = models.PositiveIntegerField(default=0)
    total_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['warehouse']),
        ]

    def __str__(self):
        return self.reference

    @property
    def total_items(self):
        return self.items.count()

    @property
    def packed_items(self):
        return self.items.filter(is_packed=True).count()


class PackingItem(models.Model):
    packing_list = models.ForeignKey(PackingList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    packed_quantity = models.PositiveIntegerField(default=0)
    package_number = models.CharField(max_length=20, blank=True, default='')
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_packed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.product.name}: {self.packed_quantity}/{self.quantity}"


class Shipment(models.Model):
    STATUS_CHOICES = [
        ('ready', 'Ready to Ship'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shipments')
    reference = models.CharField(max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='shipments')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='shipments')
    packing_list = models.ForeignKey(PackingList, on_delete=models.SET_NULL, null=True, blank=True, related_name='shipments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
    carrier = models.CharField(max_length=100, blank=True, default='')
    driver = models.CharField(max_length=100, blank=True, default='')
    tracking_number = models.CharField(max_length=100, blank=True, default='')
    shipped_date = models.DateField(null=True, blank=True)
    delivered_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_shipments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['tracking_number']),
        ]

    def __str__(self):
        return self.reference

    @property
    def package_count(self):
        return self.packages.count()

    @property
    def total_weight(self):
        return self.packages.aggregate(total=models.Sum('weight'))['total'] or 0


class ShipmentPackage(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='packages')
    package_number = models.CharField(max_length=20)
    barcode = models.CharField(max_length=100, blank=True, default='')
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.shipment.reference} - {self.package_number}"

    @property
    def items(self):
        return PackingItem.objects.filter(
            packing_list__shipment=self.shipment,
            package_number=self.package_number,
            is_packed=True,
        )


class Transfer(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('picking', 'Picking'),
        ('shipped', 'Shipped'),
        ('in_transit', 'In Transit'),
        ('received', 'Received'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='transfers')
    reference = models.CharField(max_length=50)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='incoming_transfers')
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_from')
    to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_to')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=10, choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal')
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_transfers')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    shipped_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='shipped_transfers')
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')
    shipped_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.reference}: {self.from_warehouse} → {self.to_warehouse}"


class TransferItem(models.Model):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    shipped_quantity = models.PositiveIntegerField(default=0)
    received_quantity = models.PositiveIntegerField(default=0)
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_from')
    to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_to')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['product__name']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def remaining_quantity(self):
        return max(0, self.quantity - self.shipped_quantity)


class WarehouseTask(models.Model):
    TASK_TYPES = [
        ('receiving', 'Receiving'),
        ('putaway', 'Put-away'),
        ('picking', 'Picking'),
        ('packing', 'Packing'),
        ('shipping', 'Shipping'),
        ('counting', 'Counting'),
        ('transfer', 'Transfer'),
        ('returns', 'Returns'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='warehouse_tasks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='tasks')
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    reference = models.CharField(max_length=50, blank=True, default='')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='warehouse_tasks')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_warehouse_tasks')
    reference_type = models.CharField(max_length=50, blank=True, default='')
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['task_type']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
        ]

    def __str__(self):
        return f"[{self.get_task_type_display()}] {self.title}"


class DamagedStock(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='damaged_stock')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='damaged_records')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='damaged_stock')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='damaged_stock')
    quantity = models.PositiveIntegerField()
    reason = models.TextField(blank=True, default='')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='damaged_reports')
    reference_type = models.CharField(max_length=50, blank=True, default='')
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['warehouse']),
        ]

    def __str__(self):
        return f"Damaged: {self.product.name} x {self.quantity}"


class QuarantineStock(models.Model):
    STATUS_CHOICES = [
        ('quarantined', 'Quarantined'),
        ('inspected', 'Inspected'),
        ('released', 'Released'),
        ('disposed', 'Disposed'),
        ('returned_to_supplier', 'Returned to Supplier'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quarantine_stock')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='quarantine_records')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='quarantine_stock')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='quarantine_stock')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='quarantine_records')
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='quarantined')
    reason = models.TextField(blank=True, default='')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='quarantine_reports')
    inspected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='quarantine_inspections')
    reference_type = models.CharField(max_length=50, blank=True, default='')
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['product']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Quarantine: {self.product.name} x {self.quantity}"
