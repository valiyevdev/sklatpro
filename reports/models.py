from django.db import models
from django.conf import settings


class SavedReport(models.Model):
    REPORT_TYPES = [
        ('sales_summary', 'Sales Summary'),
        ('sales_trend', 'Sales Trend'),
        ('sales_by_product', 'Sales by Product'),
        ('sales_by_customer', 'Sales by Customer'),
        ('sales_by_employee', 'Sales by Employee'),
        ('purchase_summary', 'Purchase Summary'),
        ('purchase_by_supplier', 'Purchase by Supplier'),
        ('inventory_summary', 'Inventory Summary'),
        ('stock_movement', 'Stock Movement'),
        ('stock_by_warehouse', 'Stock by Warehouse'),
        ('finance_summary', 'Finance Summary'),
        ('cash_flow', 'Cash Flow'),
        ('budget_vs_actual', 'Budget vs Actual'),
        ('abc_analysis', 'ABC Analysis'),
        ('xyz_analysis', 'XYZ Analysis'),
        ('abc_xyz_matrix', 'ABC/XYZ Matrix'),
        ('rfm_analysis', 'RFM Analysis'),
        ('customer_analytics', 'Customer Analytics'),
        ('supplier_analytics', 'Supplier Analytics'),
        ('product_profitability', 'Product Profitability'),
        ('order_analytics', 'Order Analytics'),
        ('pos_analytics', 'POS Analytics'),
        ('task_analytics', 'Task Analytics'),
        ('warehouse_analytics', 'Warehouse Analytics'),
        ('kpi_summary', 'KPI Summary'),
    ]
    VISIBILITY = [
        ('private', 'Private'),
        ('team', 'Team'),
        ('company', 'Company'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='saved_reports')
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=40, choices=REPORT_TYPES)
    filters = models.JSONField(default=dict, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY, default='private')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class ReportSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='report_schedules')
    saved_report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.saved_report.name} ({self.frequency})'
