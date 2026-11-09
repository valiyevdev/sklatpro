from django import forms
from .models import GTIN, MarkingCode, Aggregation


from core.lang import ph

class GTINForm(forms.ModelForm):
    class Meta:
        model = GTIN
        fields = ['product', 'gtin', 'format_type', 'is_primary', 'is_active']
        widgets = {
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'gtin': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_gtin'),
            }),
            'format_type': forms.Select(attrs={'class': 'input-pro'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MarkingCodeForm(forms.ModelForm):
    class Meta:
        model = MarkingCode
        fields = [
            'code', 'product', 'gtin', 'serial_number', 'batch',
            'status', 'supplier', 'purchase', 'warehouse', 'location',
            'verification_notes',
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_marking_code'),
            }),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'gtin': forms.Select(attrs={'class': 'input-pro'}),
            'serial_number': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_serial_optional'),
            }),
            'batch': forms.Select(attrs={'class': 'input-pro'}),
            'status': forms.Select(attrs={'class': 'input-pro'}),
            'supplier': forms.Select(attrs={'class': 'input-pro'}),
            'purchase': forms.Select(attrs={'class': 'input-pro'}),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
            'verification_notes': forms.Textarea(attrs={
                'class': 'input-pro',
                'rows': 3,
                'placeholder': ph('ph_extra_notes'),
            }),
        }


class AggregationForm(forms.ModelForm):
    class Meta:
        model = Aggregation
        fields = ['parent_code', 'product', 'quantity', 'warehouse', 'location']
        widgets = {
            'parent_code': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_primary_aggr_code'),
            }),
            'product': forms.Select(attrs={'class': 'input-pro'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'input-pro',
                'min': '1',
            }),
            'warehouse': forms.Select(attrs={'class': 'input-pro'}),
            'location': forms.Select(attrs={'class': 'input-pro'}),
        }


class CodeValidateForm(forms.Form):
    code_input = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'input-pro',
            'placeholder': ph('ph_code_or_scan'),
            'autofocus': True,
        }),
    )
