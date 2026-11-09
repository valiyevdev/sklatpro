from django import forms
from .models import Transaction, StockAdjustment, StockAdjustmentItem, InventoryCount, InventoryCountItem
from products.models import Product
from warehouses.models import Warehouse


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['product', 'quantity', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro', 'min': 1}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['warehouse', 'reason', 'notes']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'reason': forms.TextInput(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }


class StockAdjustmentItemForm(forms.ModelForm):
    class Meta:
        model = StockAdjustmentItem
        fields = ['product', 'actual_quantity', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'actual_quantity': forms.NumberInput(attrs={'class': 'input-pro'}),
            'notes': forms.TextInput(attrs={'class': 'input-pro'}),
        }


class InventoryCountForm(forms.ModelForm):
    class Meta:
        model = InventoryCount
        fields = ['warehouse', 'assigned_to', 'notes']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'assigned_to': forms.Select(attrs={'class': 'input-pro'}),
            'notes': forms.Textarea(attrs={'class': 'input-pro', 'rows': 3}),
        }


class InventoryCountItemForm(forms.ModelForm):
    class Meta:
        model = InventoryCountItem
        fields = ['actual_quantity', 'notes']
        widgets = {
            'actual_quantity': forms.NumberInput(attrs={'class': 'input-pro', 'min': 0}),
            'notes': forms.TextInput(attrs={'class': 'input-pro'}),
        }
