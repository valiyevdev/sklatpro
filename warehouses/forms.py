from django import forms
from .models import (
    Warehouse, Zone, Location, Batch, SerialNumber,
    Receiving, ReceivingItem, PutAway, PutAwayItem,
    PickingList, PickingItem, PackingList, PackingItem,
    Shipment, ShipmentPackage, Transfer, TransferItem,
    WarehouseTask, DamagedStock, QuarantineStock
)


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'code': forms.TextInput(attrs={'class': 'input-pro'}),
            'description': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'address': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'input-pro'}),
            'country': forms.TextInput(attrs={'class': 'input-pro'}),
            'phone': forms.TextInput(attrs={'class': 'input-pro'}),
            'email': forms.EmailInput(attrs={'class': 'input-pro'}),
            'manager': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse_type': forms.Select(attrs={'class': 'input-pro'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'is_main': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'capacity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'working_hours': forms.TextInput(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['address'].required = False
        self.fields['city'].required = False
        self.fields['country'].required = False
        self.fields['phone'].required = False
        self.fields['email'].required = False
        self.fields['manager'].required = False
        self.fields['capacity'].required = False
        self.fields['working_hours'].required = False


class ZoneForm(forms.ModelForm):
    class Meta:
        model = Zone
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'code': forms.TextInput(attrs={'class': 'input-pro'}),
            'zone_type': forms.Select(attrs={'class': 'input-pro'}),
            'description': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'temperature_controlled': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'zone': forms.Select(attrs={'class': 'input-pro'}),
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'code': forms.TextInput(attrs={'class': 'input-pro'}),
            'location_type': forms.Select(attrs={'class': 'input-pro'}),
            'rack': forms.TextInput(attrs={'class': 'input-pro'}),
            'shelf': forms.TextInput(attrs={'class': 'input-pro'}),
            'bin_code': forms.TextInput(attrs={'class': 'input-pro'}),
            'aisle': forms.TextInput(attrs={'class': 'input-pro'}),
            'capacity_qty': forms.NumberInput(attrs={'class': 'input-pro'}),
            'capacity_weight': forms.NumberInput(attrs={'class': 'input-pro'}),
            'capacity_volume': forms.NumberInput(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'barcode': forms.TextInput(attrs={'class': 'input-pro'}),
            'qr_code': forms.TextInput(attrs={'class': 'input-pro'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['zone'].required = False
        self.fields['rack'].required = False
        self.fields['shelf'].required = False
        self.fields['bin_code'].required = False
        self.fields['aisle'].required = False
        self.fields['capacity_qty'].required = False
        self.fields['capacity_weight'].required = False
        self.fields['capacity_volume'].required = False
        self.fields['barcode'].required = False
        self.fields['qr_code'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['zone'].queryset = Zone.objects.filter(company=self.company)


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        exclude = ['company', 'created_at', 'updated_at', 'reserved_quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'batch_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'supplier': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'receipt_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'manufacturing_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['supplier'].required = False
        self.fields['location'].required = False
        self.fields['manufacturing_date'].required = False
        self.fields['expiry_date'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['location'].queryset = Location.objects.filter(company=self.company)


class SerialNumberForm(forms.ModelForm):
    class Meta:
        model = SerialNumber
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'serial': forms.TextInput(attrs={'class': 'input-pro'}),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'sale': forms.Select(attrs={'class': 'input-pro'}),
            'purchase': forms.Select(attrs={'class': 'input-pro'}),
            'transfer': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['batch'].required = False
        self.fields['warehouse'].required = False
        self.fields['location'].required = False
        self.fields['sale'].required = False
        self.fields['purchase'].required = False
        self.fields['transfer'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['location'].queryset = Location.objects.filter(company=self.company)
            self.fields['batch'].queryset = Batch.objects.filter(company=self.company)


class ReceivingForm(forms.ModelForm):
    class Meta:
        model = Receiving
        exclude = ['company', 'created_at', 'updated_at', 'completed_at', 'started_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'purchase': forms.Select(attrs={'class': 'input-pro'}),
            'supplier': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'expected_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'actual_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'assigned_to': forms.Select(attrs={'class': 'input-pro'}),
            'created_by': forms.Select(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['purchase'].required = False
        self.fields['supplier'].required = False
        self.fields['actual_date'].required = False
        self.fields['notes'].required = False
        self.fields['assigned_to'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)


class ReceivingItemForm(forms.ModelForm):
    class Meta:
        model = ReceivingItem
        fields = '__all__'
        widgets = {
            'receiving': forms.Select(attrs={'class': 'input-pro'}),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'expected_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'received_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'damaged_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'rejected_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'batch_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'expiry_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['received_quantity'].required = False
        self.fields['damaged_quantity'].required = False
        self.fields['rejected_quantity'].required = False
        self.fields['batch'].required = False
        self.fields['batch_number'].required = False
        self.fields['expiry_date'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['batch'].queryset = Batch.objects.filter(company=self.company)


class PutAwayForm(forms.ModelForm):
    class Meta:
        model = PutAway
        exclude = ['company', 'created_at', 'updated_at', 'started_at', 'completed_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'receiving': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'assigned_to': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['notes'].required = False
        self.fields['assigned_to'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['receiving'].queryset = Receiving.objects.filter(company=self.company)


class PickingListForm(forms.ModelForm):
    class Meta:
        model = PickingList
        exclude = ['company', 'created_at', 'updated_at', 'started_at', 'completed_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'sale': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'priority': forms.Select(attrs={'class': 'input-pro'}),
            'strategy': forms.Select(attrs={'class': 'input-pro'}),
            'picker': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['notes'].required = False
        self.fields['picker'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)


class PickingItemForm(forms.ModelForm):
    class Meta:
        model = PickingItem
        fields = '__all__'
        widgets = {
            'picking_list': forms.Select(attrs={'class': 'input-pro'}),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'picked_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'is_picked': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'is_short_pick': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['picked_quantity'].required = False
        self.fields['location'].required = False
        self.fields['batch'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['location'].queryset = Location.objects.filter(company=self.company)
            self.fields['batch'].queryset = Batch.objects.filter(company=self.company)


class PackingListForm(forms.ModelForm):
    class Meta:
        model = PackingList
        exclude = ['company', 'created_at', 'updated_at', 'started_at', 'completed_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'picking_list': forms.Select(attrs={'class': 'input-pro'}),
            'sale': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'packer': forms.Select(attrs={'class': 'input-pro'}),
            'package_count': forms.NumberInput(attrs={'class': 'input-pro'}),
            'total_weight': forms.NumberInput(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['picking_list'].required = False
        self.fields['packer'].required = False
        self.fields['package_count'].required = False
        self.fields['total_weight'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['picking_list'].queryset = PickingList.objects.filter(company=self.company)


class PackingItemForm(forms.ModelForm):
    class Meta:
        model = PackingItem
        fields = '__all__'
        widgets = {
            'packing_list': forms.Select(attrs={'class': 'input-pro'}),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'packed_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'package_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'weight': forms.NumberInput(attrs={'class': 'input-pro'}),
            'is_packed': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['packed_quantity'].required = False
        self.fields['package_number'].required = False
        self.fields['weight'].required = False
        self.fields['notes'].required = False


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'sale': forms.Select(attrs={'class': 'input-pro'}),
            'packing_list': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'carrier': forms.TextInput(attrs={'class': 'input-pro'}),
            'driver': forms.TextInput(attrs={'class': 'input-pro'}),
            'tracking_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'shipped_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'delivered_date': forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'created_by': forms.Select(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['packing_list'].required = False
        self.fields['carrier'].required = False
        self.fields['driver'].required = False
        self.fields['tracking_number'].required = False
        self.fields['shipped_date'].required = False
        self.fields['delivered_date'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['packing_list'].queryset = PackingList.objects.filter(company=self.company)


class ShipmentPackageForm(forms.ModelForm):
    class Meta:
        model = ShipmentPackage
        fields = '__all__'
        widgets = {
            'shipment': forms.Select(attrs={'class': 'input-pro'}),
            'package_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'barcode': forms.TextInput(attrs={'class': 'input-pro'}),
            'weight': forms.NumberInput(attrs={'class': 'input-pro'}),
            'length': forms.NumberInput(attrs={'class': 'input-pro'}),
            'width': forms.NumberInput(attrs={'class': 'input-pro'}),
            'height': forms.NumberInput(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['package_number'].required = False
        self.fields['barcode'].required = False
        self.fields['weight'].required = False
        self.fields['length'].required = False
        self.fields['width'].required = False
        self.fields['height'].required = False
        self.fields['notes'].required = False


class TransferForm(forms.ModelForm):
    class Meta:
        model = Transfer
        exclude = ['company', 'created_at', 'updated_at', 'approved_by', 'shipped_by', 'received_by', 'shipped_at', 'received_at']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'from_warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'to_warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'from_location': forms.Select(attrs={'class': 'input-pro'}),
            'to_location': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'priority': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['from_location'].required = False
        self.fields['to_location'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['from_warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['to_warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['from_location'].queryset = Location.objects.filter(company=self.company)
            self.fields['to_location'].queryset = Location.objects.filter(company=self.company)


class TransferItemForm(forms.ModelForm):
    class Meta:
        model = TransferItem
        fields = '__all__'
        widgets = {
            'transfer': forms.Select(attrs={'class': 'input-pro'}),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'shipped_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'received_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'from_location': forms.Select(attrs={'class': 'input-pro'}),
            'to_location': forms.Select(attrs={'class': 'input-pro'}),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['shipped_quantity'].required = False
        self.fields['received_quantity'].required = False
        self.fields['from_location'].required = False
        self.fields['to_location'].required = False
        self.fields['batch'].required = False
        self.fields['notes'].required = False
        if self.company:
            self.fields['from_location'].queryset = Location.objects.filter(company=self.company)
            self.fields['to_location'].queryset = Location.objects.filter(company=self.company)
            self.fields['batch'].queryset = Batch.objects.filter(company=self.company)


class WarehouseTaskForm(forms.ModelForm):
    class Meta:
        model = WarehouseTask
        exclude = ['company', 'created_at', 'updated_at', 'started_at', 'completed_at', 'reference_type', 'reference_id']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'task_type': forms.Select(attrs={'class': 'input-pro'}),
            'reference': forms.TextInput(attrs={'class': 'input-pro'}),
            'title': forms.TextInput(attrs={'class': 'input-pro'}),
            'description': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'priority': forms.Select(attrs={'class': 'input-pro'}),
            'assigned_to': forms.Select(attrs={'class': 'input-pro'}),
            'created_by': forms.Select(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['description'].required = False
        self.fields['assigned_to'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)


class DamagedStockForm(forms.ModelForm):
    class Meta:
        model = DamagedStock
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'reason': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'reported_by': forms.Select(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['location'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['location'].queryset = Location.objects.filter(company=self.company)


class QuarantineStockForm(forms.ModelForm):
    class Meta:
        model = QuarantineStock
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'reason': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
            'reported_by': forms.Select(attrs={'class': 'input-pro'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['location'].required = False
        self.fields['batch'].required = False
        if self.company:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(company=self.company)
            self.fields['location'].queryset = Location.objects.filter(company=self.company)
            self.fields['batch'].queryset = Batch.objects.filter(company=self.company)
