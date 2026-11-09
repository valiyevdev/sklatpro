from django import forms
from .models import (CustomerDebt, SupplierDebt, Payment,
    FinancialAccount, FinancialTransaction, AccountTransfer,
    ExpenseCategory, IncomeCategory, Budget)

from core.lang import ph

class CustomerDebtForm(forms.ModelForm):
    class Meta:
        model = CustomerDebt
        fields = ['customer_name', 'phone_number', 'debt_amount', 'due_date', 'notes']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': ph('ph_customer_name'),
                'required': True
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': ph('ph_phone')
            }),
            'debt_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': ph('ph_extra_notes')
            }),
        }
    
    def clean_customer_name(self):
        name = self.cleaned_data.get('customer_name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError('Mijoz nomi kamida 2 ta belgidan iborat bo\'lishi kerak.')
        return name.strip()
    
    def clean_debt_amount(self):
        amount = self.cleaned_data.get('debt_amount')
        if amount is None or amount <= 0:
            raise forms.ValidationError('Qarz miqdori musbat bo\'lishi kerak.')
        return amount

class SupplierDebtForm(forms.ModelForm):
    class Meta:
        model = SupplierDebt
        fields = ['supplier_name', 'amount_owed', 'due_date', 'notes']
        widgets = {
            'supplier_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': ph('ph_supplier_name'),
                'required': True
            }),
            'amount_owed': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': ph('ph_extra_notes')
            }),
        }
    
    def clean_supplier_name(self):
        name = self.cleaned_data.get('supplier_name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError('Taminotchi nomi kamida 2 ta belgidan iborat bo\'lishi kerak.')
        return name.strip()
    
    def clean_amount_owed(self):
        amount = self.cleaned_data.get('amount_owed')
        if amount is None or amount <= 0:
            raise forms.ValidationError('Qarz miqdori musbat bo\'lishi kerak.')
        return amount

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'payment_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': ph('ph_extra_notes')
            }),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise forms.ValidationError('To\'lov miqdori musbat bo\'lishi kerak.')
        return amount


class FinancialAccountForm(forms.ModelForm):
    class Meta:
        model = FinancialAccount
        fields = ['name', 'code', 'account_type', 'currency', 'opening_balance', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_account_name')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_account_code')}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'opening_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = ['date', 'txn_type', 'direction', 'amount', 'account', 'category', 'reference_number', 'payment_method', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'txn_type': forms.Select(attrs={'class': 'form-control'}),
            'direction': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'account': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AccountTransferForm(forms.ModelForm):
    class Meta:
        model = AccountTransfer
        fields = ['date', 'from_account', 'to_account', 'amount', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'from_account': forms.Select(attrs={'class': 'form-control'}),
            'to_account': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class IncomeCategoryForm(forms.ModelForm):
    class Meta:
        model = IncomeCategory
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['name', 'category', 'period_type', 'year', 'month', 'planned_amount', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'period_type': forms.Select(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'month': forms.NumberInput(attrs={'class': 'form-control'}),
            'planned_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
