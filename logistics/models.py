from django.db import models
from django.conf import settings
from django.utils import timezone


class Driver(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('on_route', 'On Route'),
        ('on_break', 'On Break'),
        ('unavailable', 'Unavailable'),
        ('off_duty', 'Off Duty'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='drivers')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_profile')
    employee_id = models.CharField(max_length=50, blank=True, default='')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    license_number = models.CharField(max_length=50, blank=True, default='')
    license_category = models.CharField(max_length=20, blank=True, default='')
    license_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class Vehicle(models.Model):
    TYPE_CHOICES = [
        ('car', 'Car'),
        ('van', 'Van'),
        ('truck', 'Truck'),
        ('refrigerated', 'Refrigerated Truck'),
        ('motorcycle', 'Motorcycle'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('on_route', 'On Route'),
        ('maintenance', 'Maintenance'),
        ('inactive', 'Inactive'),
    ]
    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
        ('gas', 'Gas (CNG/LPG)'),
        ('other', 'Other'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='vehicles')
    vehicle_number = models.CharField(max_length=50)
    plate_number = models.CharField(max_length=30, blank=True, default='')
    vehicle_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='van')
    brand = models.CharField(max_length=100, blank=True, default='')
    model_name = models.CharField(max_length=100, blank=True, default='')
    year = models.PositiveIntegerField(null=True, blank=True)
    max_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_volume_m3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_packages = models.PositiveIntegerField(default=0)
    fuel_type = models.CharField(max_length=20, choices=FUEL_CHOICES, default='diesel')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    current_driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_vehicles')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vehicle_number']

    def __str__(self):
        return f'{self.vehicle_number} ({self.plate_number})' if self.plate_number else self.vehicle_number


class DeliveryZone(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='delivery_zones')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, blank=True, default='')
    description = models.TextField(blank=True, default='')
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_time_minutes = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Route(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('assigned', 'Assigned'),
        ('ready', 'Ready'),
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='routes')
    reference = models.CharField(max_length=50, unique=True)
    route_date = models.DateField(default=timezone.now)
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name='routes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    planned_start = models.TimeField(null=True, blank=True)
    planned_end = models.TimeField(null=True, blank=True)
    actual_start = models.TimeField(null=True, blank=True)
    actual_end = models.TimeField(null=True, blank=True)
    estimated_distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_duration_minutes = models.PositiveIntegerField(default=0)
    actual_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_routes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-route_date', 'reference']

    def __str__(self):
        return f'{self.reference} - {self.route_date}'

    @property
    def total_stops(self):
        return self.stops.count()

    @property
    def completed_stops(self):
        return self.stops.filter(status='completed').count()

    @property
    def failed_stops(self):
        return self.stops.filter(status='failed').count()

    @property
    def progress_percent(self):
        total = self.total_stops
        if total == 0:
            return 0
        return int((self.completed_stops / total) * 100)


class RouteStop(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='route_stops')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    sequence = models.PositiveIntegerField(default=0)
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='route_stops')
    customer_name = models.CharField(max_length=200, blank=True, default='')
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    contact_name = models.CharField(max_length=100, blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    delivery_instructions = models.TextField(blank=True, default='')
    expected_arrival = models.TimeField(null=True, blank=True)
    actual_arrival = models.TimeField(null=True, blank=True)
    actual_departure = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    packages_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['route', 'sequence']

    def __str__(self):
        name = self.customer_name or (str(self.customer) if self.customer else 'Unknown')
        return f'{self.route.reference} - Stop {self.sequence}: {name}'


class Shipment(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('assigned', 'Assigned'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('at_stop', 'At Stop'),
        ('delivered', 'Delivered'),
        ('partially_delivered', 'Partially Delivered'),
        ('failed', 'Failed'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    METHOD_CHOICES = [
        ('own_vehicle', 'Own Vehicle'),
        ('third_party', 'Third-Party Courier'),
        ('pickup', 'Pickup'),
        ('express', 'Express'),
        ('scheduled', 'Scheduled Delivery'),
        ('other', 'Other'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='logistics_shipments')
    reference = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_shipments')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_shipments')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_shipments')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_shipments')
    delivery_address = models.TextField(blank=True, default='')
    delivery_city = models.CharField(max_length=100, blank=True, default='')
    delivery_contact_name = models.CharField(max_length=100, blank=True, default='')
    delivery_contact_phone = models.CharField(max_length=30, blank=True, default='')
    delivery_instructions = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    total_packages = models.PositiveIntegerField(default=0)
    total_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_volume_m3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='shipments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_shipments')
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='shipments')
    route_stop = models.ForeignKey(RouteStop, on_delete=models.SET_NULL, null=True, blank=True, related_name='shipments')
    delivery_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='own_vehicle')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')
    tracking_number = models.CharField(max_length=100, blank=True, default='')
    carrier = models.CharField(max_length=100, blank=True, default='')
    external_shipment_id = models.CharField(max_length=100, blank=True, default='')
    planned_dispatch_at = models.DateTimeField(null=True, blank=True)
    actual_dispatch_at = models.DateTimeField(null=True, blank=True)
    expected_delivery_at = models.DateTimeField(null=True, blank=True)
    actual_delivery_at = models.DateTimeField(null=True, blank=True)
    delivery_time_window_start = models.TimeField(null=True, blank=True)
    delivery_time_window_end = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_logistics_shipments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} - {self.get_status_display()}'


class ShipmentPackage(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='shipment_packages')
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='packages')
    package_number = models.CharField(max_length=50, blank=True, default='')
    barcode = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    length_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    width_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    height_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shipment', 'package_number']

    def __str__(self):
        return f'{self.shipment.reference} - {self.package_number or self.pk}'


class ShipmentItem(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='shipment_items')
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='shipment_items')
    product_name = models.CharField(max_length=200, blank=True, default='')
    ordered_quantity = models.PositiveIntegerField(default=0)
    packed_quantity = models.PositiveIntegerField(default=0)
    shipped_quantity = models.PositiveIntegerField(default=0)
    delivered_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    batch_number = models.CharField(max_length=100, blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shipment', 'pk']

    def __str__(self):
        name = self.product_name or (str(self.product) if self.product else 'Unknown')
        return f'{self.shipment.reference} - {name}'

    @property
    def remaining_quantity(self):
        return self.ordered_quantity - self.delivered_quantity - self.returned_quantity


class Delivery(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('delivered', 'Delivered'),
        ('partially_delivered', 'Partially Delivered'),
        ('failed', 'Failed'),
        ('rescheduled', 'Rescheduled'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='deliveries')
    reference = models.CharField(max_length=50, unique=True)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='deliveries')
    route_stop = models.ForeignKey(RouteStop, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    delivery_address = models.TextField(blank=True, default='')
    delivery_city = models.CharField(max_length=100, blank=True, default='')
    contact_name = models.CharField(max_length=100, blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    delivery_instructions = models.TextField(blank=True, default='')
    expected_time = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    actual_departure = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    ordered_quantity = models.PositiveIntegerField(default=0)
    delivered_quantity = models.PositiveIntegerField(default=0)
    failure_reason = models.CharField(max_length=50, blank=True, default='')
    failure_notes = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_logistics_deliveries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} - {self.get_status_display()}'


class DeliveryStatusEvent(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='delivery_events')
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='status_events')
    from_status = models.CharField(max_length=20, blank=True, default='')
    to_status = models.CharField(max_length=20)
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['delivery', 'timestamp']

    def __str__(self):
        return f'{self.delivery.reference}: {self.from_status} → {self.to_status}'


class ShipmentTrackingEvent(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='tracking_events')
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    event_type = models.CharField(max_length=50)
    description = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['shipment', 'timestamp']

    def __str__(self):
        return f'{self.shipment.reference}: {self.event_type}'


class DriverLocation(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    speed = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_locations')
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.driver} - {self.timestamp}'


class ProofOfDelivery(models.Model):
    TYPE_CHOICES = [
        ('signature', 'Signature'),
        ('photo', 'Photo'),
        ('recipient_name', 'Recipient Name'),
        ('otp', 'OTP'),
        ('delivery_code', 'Delivery Code'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('captured', 'Captured'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='proofs_of_delivery')
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='proofs_of_delivery')
    proof_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recipient_name = models.CharField(max_length=200, blank=True, default='')
    signature_data = models.TextField(blank=True, default='', help_text='Base64 encoded signature image')
    photo = models.ImageField(upload_to='delivery_proofs/', blank=True, null=True)
    otp_code = models.CharField(max_length=10, blank=True, default='')
    delivery_code = models.CharField(max_length=20, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    captured_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    captured_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='captured_proofs')
    device_info = models.CharField(max_length=200, blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.delivery.reference} - {self.get_proof_type_display()}'


class DeliveryCost(models.Model):
    CATEGORY_CHOICES = [
        ('fuel', 'Fuel'),
        ('driver', 'Driver Cost'),
        ('courier', 'Third-Party Courier'),
        ('tolls', 'Tolls'),
        ('parking', 'Parking'),
        ('other', 'Other'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='delivery_costs')
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, null=True, blank=True, related_name='costs')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, null=True, blank=True, related_name='costs')
    delivery = models.ForeignKey(Delivery, on_delete=models.SET_NULL, null=True, blank=True, related_name='costs')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='UZS')
    cost_date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True, default='')
    receipt = models.ImageField(upload_to='delivery_costs/', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    finance_transaction = models.ForeignKey('finance.FinancialTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_costs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cost_date']

    def __str__(self):
        return f'{self.get_category_display()} - {self.amount} {self.currency}'


class DeliveryReschedule(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='delivery_reschedules')
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='reschedules')
    old_expected_time = models.DateTimeField(null=True, blank=True)
    new_expected_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Reschedule: {self.delivery.reference}'


class CourierProvider(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='courier_providers')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, blank=True, default='')
    api_url = models.URLField(blank=True, default='')
    api_key = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DeliveryTimeWindow(models.Model):
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='delivery_time_windows')
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f'{self.name} ({self.start_time} - {self.end_time})'
