from django.urls import path
from . import views

app_name = 'logistics'

urlpatterns = [
    # Dashboard
    path('', views.logistics_dashboard, name='logistics_dashboard'),

    # Shipments
    path('shipments/', views.shipment_list, name='shipment_list'),
    path('shipments/create/', views.shipment_create, name='shipment_create'),
    path('shipments/<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('shipments/<int:pk>/edit/', views.shipment_update, name='shipment_update'),
    path('shipments/<int:pk>/status/', views.shipment_update_status, name='shipment_update_status'),
    path('shipments/<int:pk>/delete/', views.shipment_delete, name='shipment_delete'),
    path('shipments/<int:pk>/add-package/', views.shipment_add_package, name='shipment_add_package'),
    path('shipments/export/', views.shipment_export, name='shipment_export'),

    # Deliveries
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/create/', views.delivery_create, name='delivery_create'),
    path('deliveries/<int:pk>/', views.delivery_detail, name='delivery_detail'),
    path('deliveries/<int:pk>/status/', views.delivery_update_status, name='delivery_update_status'),
    path('deliveries/<int:pk>/reschedule/', views.delivery_reschedule, name='delivery_reschedule'),
    path('deliveries/<int:pk>/return/', views.delivery_return, name='delivery_return'),
    path('deliveries/export/', views.delivery_export, name='delivery_export'),

    # Proof of Delivery
    path('deliveries/<int:delivery_pk>/pod/', views.pod_capture, name='pod_capture'),
    path('pod/<int:pk>/verify/', views.pod_verify, name='pod_verify'),

    # Drivers
    path('drivers/', views.driver_list, name='driver_list'),
    path('drivers/create/', views.driver_create, name='driver_create'),
    path('drivers/<int:pk>/', views.driver_detail, name='driver_detail'),
    path('drivers/<int:pk>/edit/', views.driver_update, name='driver_update'),
    path('drivers/<int:pk>/delete/', views.driver_delete, name='driver_delete'),
    path('drivers/<int:pk>/status/', views.driver_update_status, name='driver_update_status'),

    # Vehicles
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('vehicles/create/', views.vehicle_create, name='vehicle_create'),
    path('vehicles/<int:pk>/', views.vehicle_detail, name='vehicle_detail'),
    path('vehicles/<int:pk>/edit/', views.vehicle_update, name='vehicle_update'),
    path('vehicles/<int:pk>/delete/', views.vehicle_delete, name='vehicle_delete'),

    # Routes
    path('routes/', views.route_list, name='route_list'),
    path('routes/create/', views.route_create, name='route_create'),
    path('routes/<int:pk>/', views.route_detail, name='route_detail'),
    path('routes/<int:pk>/edit/', views.route_update, name='route_update'),
    path('routes/<int:pk>/status/', views.route_update_status, name='route_update_status'),
    path('routes/<int:pk>/add-stop/', views.route_add_stop, name='route_add_stop'),
    path('routes/<int:route_pk>/stops/<int:stop_pk>/delete/', views.route_stop_delete, name='route_stop_delete'),
    path('routes/<int:route_pk>/stops/<int:stop_pk>/status/', views.route_stop_update_status, name='route_stop_update_status'),

    # Dispatch
    path('dispatch/', views.dispatch_board, name='dispatch_board'),
    path('dispatch/assign/', views.dispatch_assign, name='dispatch_assign'),
    path('dispatch/reassign/', views.dispatch_reassign, name='dispatch_reassign'),

    # Tracking
    path('tracking/', views.tracking_list, name='tracking_list'),
    path('tracking/<int:pk>/', views.tracking_detail, name='tracking_detail'),
    path('tracking/<int:pk>/add-event/', views.tracking_add_event, name='tracking_add_event'),

    # Delivery Costs
    path('costs/', views.cost_list, name='cost_list'),
    path('costs/create/', views.cost_create, name='cost_create'),
    path('costs/<int:pk>/delete/', views.cost_delete, name='cost_delete'),

    # Reports
    path('reports/', views.logistics_reports, name='logistics_reports'),

    # Driver Mobile
    path('mobile/', views.driver_mobile, name='driver_mobile'),
    path('mobile/delivery/<int:delivery_pk>/status/', views.driver_mobile_update_status, name='driver_mobile_update_status'),
    path('location/update/', views.driver_location_update, name='driver_location_update'),

    # Delivery Zones
    path('zones/', views.zone_list, name='zone_list'),
    path('zones/create/', views.zone_create, name='zone_create'),
    path('zones/<int:pk>/edit/', views.zone_update, name='zone_update'),

    # Courier Providers
    path('couriers/', views.courier_list, name='courier_list'),
    path('couriers/create/', views.courier_create, name='courier_create'),
    path('couriers/<int:pk>/edit/', views.courier_update, name='courier_update'),

    # Time Windows
    path('time-windows/', views.time_window_list, name='time_window_list'),
    path('time-windows/create/', views.time_window_create, name='time_window_create'),
]
