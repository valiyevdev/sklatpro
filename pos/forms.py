from django import forms
from .models import POSTerminal, CashShift, POSReturn


class POSTerminalForm(forms.ModelForm):
    class Meta:
        model = POSTerminal
        fields = ['name', 'code', 'serial_number', 'warehouse', 'status', 'receipt_printer', 'cash_drawer', 'barcode_scanner', 'card_terminal', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'code': forms.TextInput(attrs={'class': 'input-pro'}),
            'serial_number': forms.TextInput(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'receipt_printer': forms.TextInput(attrs={'class': 'input-pro'}),
            'cash_drawer': forms.CheckboxInput(attrs={'class': 'input-pro-checkbox'}),
            'barcode_scanner': forms.CheckboxInput(attrs={'class': 'input-pro-checkbox'}),
            'card_terminal': forms.CheckboxInput(attrs={'class': 'input-pro-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro-checkbox'}),
        }


class CashShiftOpenForm(forms.Form):
    terminal = forms.ModelChoiceField(queryset=POSTerminal.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    opening_amount = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class CashShiftCloseForm(forms.Form):
    closing_amount = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
