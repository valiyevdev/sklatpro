from django import forms
from .models import (
    Driver, Vehicle, Route, RouteStop, Shipment, ShipmentPackage,
    ShipmentItem, Delivery, ProofOfDelivery, DeliveryCost,
    DeliveryZone, CourierProvider, DeliveryTimeWindow,
)


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ['first_name', 'last_name', 'phone', 'employee_id',
                  'license_number', 'license_category', 'license_expiry',
                  'status', 'notes', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'license_category': forms.TextInput(attrs={'class': 'form-control'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['vehicle_number', 'plate_number', 'vehicle_type', 'brand',
                  'model_name', 'year', 'max_weight_kg', 'max_volume_m3',
                  'max_packages', 'fuel_type', 'status', 'current_driver',
                  'notes', 'is_active']
        widgets = {
            'vehicle_number': forms.TextInput(attrs={'class': 'form-control'}),
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'model_name': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_volume_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_packages': forms.NumberInput(attrs={'class': 'form-control'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'current_driver': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['reference', 'route_date', 'driver', 'vehicle', 'warehouse',
                  'status', 'planned_start', 'planned_end', 'estimated_distance_km',
                  'estimated_duration_minutes', 'notes']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'route_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'driver': forms.Select(attrs={'class': 'form-select'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'planned_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'planned_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'estimated_distance_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estimated_duration_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RouteStopForm(forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = ['sequence', 'customer', 'customer_name', 'address', 'city',
                  'latitude', 'longitude', 'contact_name', 'contact_phone',
                  'delivery_instructions', 'expected_arrival', 'packages_count', 'notes']
        widgets = {
            'sequence': forms.NumberInput(attrs={'class': 'form-control'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'delivery_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'expected_arrival': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'packages_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = ['reference', 'order', 'sale', 'customer', 'warehouse',
                  'delivery_address', 'delivery_city', 'delivery_contact_name',
                  'delivery_contact_phone', 'delivery_instructions',
                  'latitude', 'longitude', 'total_packages', 'total_weight_kg',
                  'total_volume_m3', 'driver', 'vehicle', 'route',
                  'delivery_method', 'priority', 'status',
                  'tracking_number', 'carrier',
                  'planned_dispatch_at', 'expected_delivery_at',
                  'delivery_time_window_start', 'delivery_time_window_end', 'notes']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.Select(attrs={'class': 'form-select'}),
            'sale': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'delivery_city': forms.TextInput(attrs={'class': 'form-control'}),
            'delivery_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'delivery_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'delivery_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'total_packages': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_volume_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'driver': forms.Select(attrs={'class': 'form-select'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'route': forms.Select(attrs={'class': 'form-select'}),
            'delivery_method': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'carrier': forms.TextInput(attrs={'class': 'form-control'}),
            'planned_dispatch_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expected_delivery_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'delivery_time_window_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'delivery_time_window_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ShipmentPackageForm(forms.ModelForm):
    class Meta:
        model = ShipmentPackage
        fields = ['package_number', 'barcode', 'description', 'weight_kg',
                  'length_cm', 'width_cm', 'height_cm', 'quantity']
        widgets = {
            'package_number': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'length_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'width_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['reference', 'shipment', 'route_stop', 'customer',
                  'delivery_address', 'delivery_city', 'contact_name',
                  'contact_phone', 'delivery_instructions',
                  'expected_time', 'status', 'driver', 'vehicle',
                  'ordered_quantity', 'delivered_quantity',
                  'failure_reason', 'failure_notes', 'notes']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'shipment': forms.Select(attrs={'class': 'form-select'}),
            'route_stop': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'delivery_city': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'delivery_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'expected_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'driver': forms.Select(attrs={'class': 'form-select'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'ordered_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'delivered_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'failure_reason': forms.Select(attrs={'class': 'form-select'}),
            'failure_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProofOfDeliveryForm(forms.ModelForm):
    class Meta:
        model = ProofOfDelivery
        fields = ['proof_type', 'recipient_name', 'notes']
        widgets = {
            'proof_type': forms.Select(attrs={'class': 'form-select'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class DeliveryCostForm(forms.ModelForm):
    class Meta:
        model = DeliveryCost
        fields = ['shipment', 'route', 'delivery', 'category', 'amount',
                  'currency', 'cost_date', 'description']
        widgets = {
            'shipment': forms.Select(attrs={'class': 'form-select'}),
            'route': forms.Select(attrs={'class': 'form-select'}),
            'delivery': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'cost_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class DeliveryZoneForm(forms.ModelForm):
    class Meta:
        model = DeliveryZone
        fields = ['name', 'code', 'description', 'base_price', 'price_per_km',
                  'estimated_time_minutes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'price_per_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estimated_time_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CourierProviderForm(forms.ModelForm):
    class Meta:
        model = CourierProvider
        fields = ['name', 'code', 'api_url', 'api_key', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'api_url': forms.URLInput(attrs={'class': 'form-control'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control'}, render_value=True),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class DeliveryTimeWindowForm(forms.ModelForm):
    class Meta:
        model = DeliveryTimeWindow
        fields = ['name', 'start_time', 'end_time', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
