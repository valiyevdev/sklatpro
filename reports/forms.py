from django import forms
from .models import SavedReport


class ReportFilterForm(forms.Form):
    preset = forms.ChoiceField(required=False, choices=[
        ('', 'All Time'),
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'),
        ('last_week', 'Last Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_quarter', 'This Quarter'),
        ('last_quarter', 'Last Quarter'),
        ('this_year', 'This Year'),
        ('last_year', 'Last Year'),
        ('custom', 'Custom Range'),
    ])
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)
    warehouse = forms.IntegerField(required=False)
    product = forms.IntegerField(required=False)
    category = forms.IntegerField(required=False)
    customer = forms.IntegerField(required=False)
    supplier = forms.IntegerField(required=False)


class SavedReportForm(forms.ModelForm):
    class Meta:
        model = SavedReport
        fields = ['name', 'report_type', 'filters', 'visibility']
        widgets = {
            'filters': forms.HiddenInput(),
        }
