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
        choices=[('', 'All Types')] + Document.TYPE_CHOICES,
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + Document.STATUS_CHOICES,
    )
    search = forms.CharField(required=False)
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        exclude = ['company', 'created_at', 'updated_at']
        widgets = {
            'template_html': forms.Textarea(attrs={'rows': 6}),
        }


class DocumentAttachmentUploadForm(forms.Form):
    file = forms.FileField()
