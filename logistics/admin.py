from django.contrib import admin
from .models import (
    Driver, Vehicle, DeliveryZone, Route, RouteStop,
    Shipment, ShipmentPackage, ShipmentItem,
    Delivery, DeliveryStatusEvent, ShipmentTrackingEvent,
    DriverLocation, ProofOfDelivery, DeliveryCost,
    DeliveryReschedule, CourierProvider, DeliveryTimeWindow,
)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'phone', 'license_number', 'status', 'company')
    list_filter = ('status', 'company')
    search_fields = ('first_name', 'last_name', 'phone', 'license_number')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_number', 'plate_number', 'vehicle_type', 'status', 'company')
    list_filter = ('vehicle_type', 'status', 'company')
    search_fields = ('vehicle_number', 'plate_number')


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'base_price', 'is_active', 'company')
    list_filter = ('is_active', 'company')


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('reference', 'route_date', 'driver', 'vehicle', 'status', 'company')
    list_filter = ('status', 'route_date', 'company')
    search_fields = ('reference',)


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('route', 'sequence', 'customer_name', 'status')
    list_filter = ('status',)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer', 'status', 'priority', 'delivery_method', 'company')
    list_filter = ('status', 'priority', 'delivery_method', 'company')
    search_fields = ('reference', 'tracking_number')


@admin.register(ShipmentPackage)
class ShipmentPackageAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'package_number', 'weight_kg', 'quantity')


@admin.register(ShipmentItem)
class ShipmentItemAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'product', 'ordered_quantity', 'delivered_quantity')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('reference', 'shipment', 'customer', 'status', 'driver', 'company')
    list_filter = ('status', 'company')
    search_fields = ('reference',)


@admin.register(DeliveryStatusEvent)
class DeliveryStatusEventAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'from_status', 'to_status', 'timestamp')


@admin.register(ShipmentTrackingEvent)
class ShipmentTrackingEventAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'event_type', 'timestamp')


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ('driver', 'latitude', 'longitude', 'timestamp')


@admin.register(ProofOfDelivery)
class ProofOfDeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'proof_type', 'status', 'captured_at')


@admin.register(DeliveryCost)
class DeliveryCostAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'category', 'amount', 'currency', 'cost_date')
    list_filter = ('category', 'currency')


@admin.register(DeliveryReschedule)
class DeliveryRescheduleAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'old_expected_time', 'new_expected_time', 'created_at')


@admin.register(CourierProvider)
class CourierProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'company')


@admin.register(DeliveryTimeWindow)
class DeliveryTimeWindowAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'is_active')
