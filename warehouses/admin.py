from django.contrib import admin
from .models import (
    Warehouse, Zone, Location, Batch, SerialNumber, StockLocation,
    Receiving, ReceivingItem, PutAway, PutAwayItem,
    PickingList, PickingItem, PackingList, PackingItem,
    Shipment, ShipmentPackage, Transfer, TransferItem,
    WarehouseTask, DamagedStock, QuarantineStock,
)


class ZoneInline(admin.TabularInline):
    model = Zone
    extra = 0


class LocationInline(admin.TabularInline):
    model = Location
    extra = 0


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'warehouse_type', 'is_active', 'manager']
    list_filter = ['company', 'warehouse_type', 'is_active']
    search_fields = ['name', 'code']
    inlines = [ZoneInline, LocationInline]


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'warehouse', 'zone_type', 'is_active']
    list_filter = ['warehouse', 'zone_type', 'is_active']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'warehouse', 'zone', 'location_type', 'rack', 'shelf', 'bin_code', 'status']
    list_filter = ['warehouse', 'location_type', 'status']
    search_fields = ['code', 'barcode']


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'product', 'warehouse', 'quantity', 'reserved_quantity', 'expiry_date', 'status']
    list_filter = ['warehouse', 'status']
    search_fields = ['batch_number']


@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ['serial', 'product', 'warehouse', 'location', 'status']
    list_filter = ['warehouse', 'status']
    search_fields = ['serial']


@admin.register(StockLocation)
class StockLocationAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'location', 'batch', 'quantity', 'reserved']
    list_filter = ['warehouse']


class ReceivingItemInline(admin.TabularInline):
    model = ReceivingItem
    extra = 0


@admin.register(Receiving)
class ReceivingAdmin(admin.ModelAdmin):
    list_display = ['reference', 'warehouse', 'supplier', 'status', 'expected_date']
    list_filter = ['warehouse', 'status']
    inlines = [ReceivingItemInline]


class PutAwayItemInline(admin.TabularInline):
    model = PutAwayItem
    extra = 0


@admin.register(PutAway)
class PutAwayAdmin(admin.ModelAdmin):
    list_display = ['reference', 'warehouse', 'status', 'assigned_to']
    list_filter = ['warehouse', 'status']
    inlines = [PutAwayItemInline]


class PickingItemInline(admin.TabularInline):
    model = PickingItem
    extra = 0


@admin.register(PickingList)
class PickingListAdmin(admin.ModelAdmin):
    list_display = ['reference', 'warehouse', 'status', 'priority', 'picker']
    list_filter = ['warehouse', 'status']
    inlines = [PickingItemInline]


class PackingItemInline(admin.TabularInline):
    model = PackingItem
    extra = 0


@admin.register(PackingList)
class PackingListAdmin(admin.ModelAdmin):
    list_display = ['reference', 'warehouse', 'status', 'packer']
    list_filter = ['warehouse', 'status']
    inlines = [PackingItemInline]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'warehouse', 'status', 'carrier', 'tracking_number', 'shipped_date']
    list_filter = ['warehouse', 'status']


@admin.register(ShipmentPackage)
class ShipmentPackageAdmin(admin.ModelAdmin):
    list_display = ['package_number', 'shipment', 'weight', 'barcode']
    list_filter = ['shipment__status']


class TransferItemInline(admin.TabularInline):
    model = TransferItem
    extra = 0


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ['reference', 'from_warehouse', 'to_warehouse', 'status', 'priority']
    list_filter = ['status']
    inlines = [TransferItemInline]


@admin.register(WarehouseTask)
class WarehouseTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'task_type', 'warehouse', 'status', 'priority', 'assigned_to']
    list_filter = ['warehouse', 'task_type', 'status']
    search_fields = ['title']


@admin.register(DamagedStock)
class DamagedStockAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'quantity', 'reason', 'reported_by']
    list_filter = ['warehouse']


@admin.register(QuarantineStock)
class QuarantineStockAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'quantity', 'status', 'reason']
    list_filter = ['warehouse', 'status']
