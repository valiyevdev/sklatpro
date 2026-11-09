from django import forms
from django.db import models
from .models import Product, Category, Brand, Unit, ProductVariant


from core.lang import ph

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'barcode', 'category_fk', 'brand', 'unit', 'status',
            'purchase_price', 'price', 'quantity', 'min_stock', 'max_stock',
            'description', 'notes', 'image',
            'supplier', 'batch_number', 'expiration_date',
            'weight', 'length', 'width', 'height',
            'shelf', 'rack', 'section',
            'product_type', 'storage_conditions', 'weight_unit',
            'netto_brutto', 'measurement_unit', 'volume',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_product_name'),
            }),
            'sku': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_auto_generate'),
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_auto_generate'),
            }),
            'category_fk': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'brand': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'unit': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'status': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'input-pro',
                'min': '0',
            }),
            'min_stock': forms.NumberInput(attrs={
                'class': 'input-pro',
                'min': '0',
            }),
            'max_stock': forms.NumberInput(attrs={
                'class': 'input-pro',
                'min': '0',
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-pro',
                'rows': 3,
            }),
            'notes': forms.Textarea(attrs={
                'class': 'input-pro',
                'rows': 2,
            }),
            'image': forms.FileInput(attrs={
                'class': 'input-pro',
                'accept': 'image/jpeg,image/png,image/webp',
            }),
            'supplier': forms.TextInput(attrs={
                'class': 'input-pro',
            }),
            'batch_number': forms.TextInput(attrs={
                'class': 'input-pro',
            }),
            'expiration_date': forms.DateInput(attrs={
                'class': 'input-pro',
                'type': 'date',
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'length': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'width': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'height': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
            'shelf': forms.TextInput(attrs={
                'class': 'input-pro',
            }),
            'rack': forms.TextInput(attrs={
                'class': 'input-pro',
            }),
            'section': forms.TextInput(attrs={
                'class': 'input-pro',
            }),
            'product_type': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'storage_conditions': forms.TextInput(attrs={
                'class': 'input-pro',
                'placeholder': ph('ph_storage_hint'),
            }),
            'weight_unit': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'netto_brutto': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'measurement_unit': forms.Select(attrs={
                'class': 'input-pro',
            }),
            'volume': forms.NumberInput(attrs={
                'class': 'input-pro',
                'step': '0.01',
                'min': '0',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['sku'].required = False
        self.fields['barcode'].required = False
        self.fields['description'].required = False
        self.fields['min_stock'].required = False
        self.fields['max_stock'].required = False
        self.fields['notes'].required = False
        self.fields['supplier'].required = False
        self.fields['batch_number'].required = False
        self.fields['expiration_date'].required = False
        self.fields['weight'].required = False
        self.fields['length'].required = False
        self.fields['width'].required = False
        self.fields['height'].required = False
        self.fields['shelf'].required = False
        self.fields['rack'].required = False
        self.fields['section'].required = False
        self.fields['storage_conditions'].required = False
        self.fields['weight_unit'].required = False
        self.fields['netto_brutto'].required = False
        self.fields['measurement_unit'].required = False
        self.fields['volume'].required = False
        if self.company:
            self.fields['category_fk'].queryset = Category.objects.filter(
                models.Q(company=self.company) | models.Q(company__isnull=True),
                is_active=True
            )
            self.fields['brand'].queryset = Brand.objects.filter(
                models.Q(company=self.company) | models.Q(company__isnull=True),
                is_active=True
            )
        self.fields['unit'].queryset = Unit.objects.filter(is_active=True)
        self.fields['category_fk'].empty_label = '-- Tanlang --'
        self.fields['brand'].empty_label = '-- Yo\'q --'
        self.fields['unit'].empty_label = '-- Tanlang --'

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError('Nomi kamida 2 ta belgidan iborat bo\'lishi kerak.')
        return name.strip()

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity < 0:
            raise forms.ValidationError('Miqdor manfiy bo\'lishi mumkin emas.')
        return quantity

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError('Narx manfiy bo\'lishi mumkin emas.')
        return price

    def clean_purchase_price(self):
        price = self.cleaned_data.get('purchase_price')
        if price is not None and price < 0:
            raise forms.ValidationError('Xarid narxi manfiy bo\'lishi mumkin emas.')
        return price


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['name', 'sku', 'barcode', 'price', 'purchase_price', 'quantity', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'sku': forms.TextInput(attrs={'class': 'input-pro', 'placeholder': ph('ph_auto_generate')}),
            'barcode': forms.TextInput(attrs={'class': 'input-pro', 'placeholder': ph('ph_auto_generate')}),
            'price': forms.NumberInput(attrs={'class': 'input-pro', 'step': '0.01', 'min': '0'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'input-pro', 'step': '0.01', 'min': '0'}),
            'quantity': forms.NumberInput(attrs={'class': 'input-pro', 'min': '0'}),
            'image': forms.FileInput(attrs={'class': 'input-pro', 'accept': 'image/jpeg,image/png,image/webp'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'parent', 'image', 'is_active', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'description': forms.Textarea(attrs={'class': 'input-pro', 'rows': 2}),
            'parent': forms.Select(attrs={'class': 'input-pro'}),
            'image': forms.FileInput(attrs={'class': 'input-pro', 'accept': 'image/*'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
            'sort_order': forms.NumberInput(attrs={'class': 'input-pro', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['parent'].empty_label = '-- Yo\'q (asosiy) --'
        if self.company:
            self.fields['parent'].queryset = Category.objects.filter(
                models.Q(company=self.company) | models.Q(company__isnull=True),
                is_active=True
            )


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'description', 'logo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-pro'}),
            'description': forms.Textarea(attrs={'class': 'input-pro', 'rows': 2}),
            'logo': forms.FileInput(attrs={'class': 'input-pro', 'accept': 'image/*'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'input-pro'}),
        }
