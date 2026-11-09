from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'warehouses'

urlpatterns = [
    path('', lambda r: redirect('warehouses:warehouse_list'), name='root'),
    path('wms/', views.wms_dashboard, name='wms_dashboard'),
    path('wms/<int:warehouse_id>/', views.warehouse_dashboard, name='warehouse_dashboard'),

    path('warehouses/', views.warehouse_list, name='warehouse_list'),
    path('warehouses/create/', views.warehouse_create, name='warehouse_create'),
    path('warehouses/<int:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('warehouses/<int:pk>/edit/', views.warehouse_update, name='warehouse_update'),
    path('warehouses/<int:pk>/delete/', views.warehouse_delete, name='warehouse_delete'),

    path('warehouses/<int:warehouse_id>/zones/', views.zone_list, name='zone_list'),
    path('warehouses/<int:warehouse_id>/zones/create/', views.zone_create, name='zone_create'),
    path('zones/<int:pk>/', views.zone_detail, name='zone_detail'),
    path('zones/<int:pk>/edit/', views.zone_update, name='zone_update'),
    path('zones/<int:pk>/delete/', views.zone_delete, name='zone_delete'),

    path('warehouses/<int:warehouse_id>/locations/', views.location_list, name='location_list'),
    path('warehouses/<int:warehouse_id>/locations/create/', views.location_create, name='location_create'),
    path('locations/<int:pk>/', views.location_detail, name='location_detail'),
    path('locations/<int:pk>/edit/', views.location_update, name='location_update'),
    path('locations/<int:pk>/delete/', views.location_delete, name='location_delete'),

    path('warehouses/<int:warehouse_id>/stock/', views.stock_location_list, name='stock_location_list'),
    path('stock-location/move/', views.stock_location_move, name='stock_location_move'),

    path('wms/receiving/', views.receiving_list, name='receiving_list'),
    path('wms/receiving/create/', views.receiving_create, name='receiving_create'),
    path('wms/receiving/<int:pk>/', views.receiving_detail, name='receiving_detail'),
    path('wms/receiving/<int:pk>/update-status/', views.receiving_update_status, name='receiving_update_status'),
    path('wms/receiving/<int:pk>/add-item/', views.receiving_add_item, name='receiving_add_item'),

    path('wms/putaway/', views.putaway_list, name='putaway_list'),
    path('wms/putaway/create/', views.putaway_create, name='putaway_create'),
    path('wms/putaway/<int:pk>/', views.putaway_detail, name='putaway_detail'),
    path('wms/putaway/<int:pk>/confirm-item/', views.putaway_confirm_item, name='putaway_confirm_item'),

    path('wms/picking/', views.picking_list, name='picking_list'),
    path('wms/picking/create/', views.picking_create, name='picking_create'),
    path('wms/picking/<int:pk>/', views.picking_detail, name='picking_detail'),
    path('wms/picking/<int:pk>/start/', views.picking_start, name='picking_start'),
    path('wms/picking/<int:pk>/confirm-item/', views.picking_confirm_item, name='picking_confirm_item'),
    path('wms/picking/<int:pk>/complete/', views.picking_complete, name='picking_complete'),

    path('wms/packing/', views.packing_list, name='packing_list'),
    path('wms/packing/create/', views.packing_create, name='packing_create'),
    path('wms/packing/<int:pk>/', views.packing_detail, name='packing_detail'),
    path('wms/packing/<int:pk>/confirm-item/', views.packing_confirm_item, name='packing_confirm_item'),
    path('wms/packing/<int:pk>/complete/', views.packing_complete, name='packing_complete'),

    path('wms/shipping/', views.shipment_list, name='shipment_list'),
    path('wms/shipping/create/', views.shipment_create, name='shipment_create'),
    path('wms/shipping/<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('wms/shipping/<int:pk>/update-status/', views.shipment_update_status, name='shipment_update_status'),

    path('warehouses/transfers/', views.transfer_list, name='transfer_list'),
    path('warehouses/transfers/create/', views.transfer_create, name='transfer_create'),
    path('warehouses/transfers/<int:pk>/', views.transfer_detail, name='transfer_detail'),
    path('warehouses/transfers/<int:pk>/update-status/', views.transfer_update_status, name='transfer_update_status'),
    path('warehouses/transfers/<int:pk>/add-item/', views.transfer_add_item, name='transfer_add_item'),

    path('wms/batches/', views.batch_list, name='batch_list'),
    path('wms/batches/create/', views.batch_create, name='batch_create'),
    path('wms/batches/<int:pk>/', views.batch_detail, name='batch_detail'),

    path('wms/serials/', views.serial_list, name='serial_list'),
    path('wms/serials/create/', views.serial_create, name='serial_create'),
    path('wms/serials/<int:pk>/', views.serial_detail, name='serial_detail'),

    path('wms/tasks/', views.task_list, name='task_list'),
    path('wms/tasks/create/', views.task_create, name='task_create'),
    path('wms/tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('wms/tasks/<int:pk>/update/', views.task_update, name='task_update'),

    path('wms/damaged/', views.damaged_list, name='damaged_list'),
    path('wms/damaged/create/', views.damaged_create, name='damaged_create'),
    path('wms/quarantine/', views.quarantine_list, name='quarantine_list'),
    path('wms/quarantine/create/', views.quarantine_create, name='quarantine_create'),
]
