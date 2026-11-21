from django import forms
from .models import (
    Document, DocumentItem, DocumentTemplate,
    DocumentAttachment,
)


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        exclude = ['company', 'created_by', 'version', 'parent_version',
                    'version_reason', 'created_at', 'updated_at']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class DocumentItemForm(forms.ModelForm):
    class Meta:
        model = DocumentItem
        exclude = ['company', 'document', 'sort_order']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'step': '0.01'}),
            'tax': forms.NumberInput(attrs={'step': '0.01'}),
        }


class DocumentFilterForm(forms.Form):
    doc_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Barcha turlar')] + Document.TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'input-pro select-pro'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Barcha holatlar')] + Document.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'input-pro select-pro'}),
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-pro', 'placeholder': 'Hujjat raqami yoki nomi...'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'input-pro', 'type': 'date'}),
    )


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'template_html': forms.Textarea(attrs={'rows': 6}),
        }


class DocumentAttachmentUploadForm(forms.Form):
    file = forms.FileField()
