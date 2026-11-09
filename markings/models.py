from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator
import uuid


class GTIN(models.Model):
    """Global Trade Item Number - product identification separate from internal SKU"""
    GTIN_FORMAT_CHOICES = [
        ('GTIN-8', 'GTIN-8'),
        ('GTIN-12', 'GTIN-12'),
        ('GTIN-13', 'GTIN-13'),
        ('GTIN-14', 'GTIN-14'),
    ]
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='gtins')
    gtin = models.CharField(max_length=14, db_index=True)
    format_type = models.CharField(max_length=10, choices=GTIN_FORMAT_CHOICES)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'gtin']
        indexes = [models.Index(fields=['company', 'product']), models.Index(fields=['gtin'])]

    def __str__(self):
        return f"{self.gtin} ({self.format_type})"

    def clean(self):
        expected = {'GTIN-8': 8, 'GTIN-12': 12, 'GTIN-13': 13, 'GTIN-14': 14}
        if self.format_type in expected and len(self.gtin) != expected[self.format_type]:
            from django.core.exceptions import ValidationError
            raise ValidationError(f'{self.format_type} must be exactly {expected[self.format_type]} digits')

    def validate_checksum(self):
        """Validate GTIN checksum (GS1 standard)"""
        digits = [int(d) for d in self.gtin]
        if len(digits) < 2:
            return False
        check_digit = digits[-1]
        total = sum(d * (3 if (len(digits) - 1 - i) % 2 == 1 else 1) for i, d in enumerate(digits[:-1]))
        remainder = total % 10
        expected = (10 - remainder) % 10
        return check_digit == expected


class MarkingCode(models.Model):
    """Marking code for product traceability"""
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('in_stock', 'In Stock'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('returned', 'Returned'),
        ('quarantined', 'Quarantined'),
        ('damaged', 'Damaged'),
        ('cancelled', 'Cancelled'),
        ('unknown', 'Unknown'),
    ]

    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    code = models.CharField(max_length=200, db_index=True)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='marking_codes')
    gtin = models.ForeignKey(GTIN, on_delete=models.SET_NULL, null=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    batch = models.ForeignKey('warehouses.Batch', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    verification_status = models.CharField(max_length=20, choices=[
        ('not_verified', 'Not Verified'),
        ('internal_verified', 'Internal Verified'),
        ('external_verified', 'External Verified'),
        ('rejected', 'Rejected'),
    ], default='not_verified')
    verification_notes = models.TextField(blank=True, null=True)

    supplier = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True)
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey('warehouses.Location', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='marking_customer_codes')
    return_ref = models.ForeignKey('sales.SaleReturn', on_delete=models.SET_NULL, null=True, blank=True)

    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'code']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'product']),
            models.Index(fields=['code']),
            models.Index(fields=['company', 'batch']),
            models.Index(fields=['company', 'serial_number']),
        ]

    def __str__(self):
        return f"{self.code} ({self.get_status_display()})"


class MarkingCodeHistory(models.Model):
    """Immutable history of every marking code status change"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    marking_code = models.ForeignKey(MarkingCode, on_delete=models.CASCADE, related_name='history')
    from_status = models.CharField(max_length=20, blank=True, null=True)
    to_status = models.CharField(max_length=20)
    event_type = models.CharField(max_length=50)
    reference_type = models.CharField(max_length=50, blank=True, null=True)
    reference_id = models.IntegerField(blank=True, null=True)
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey('warehouses.Location', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['company', 'marking_code']),
            models.Index(fields=['company', 'performed_at']),
            models.Index(fields=['marking_code', 'performed_at']),
        ]

    def __str__(self):
        return f"{self.marking_code.code}: {self.from_status} → {self.to_status}"


class Aggregation(models.Model):
    """Parent-child aggregation (e.g., unit → case → pallet)"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    parent_code = models.CharField(max_length=200, db_index=True)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('disaggregated', 'Disaggregated'),
        ('cancelled', 'Cancelled'),
    ], default='active')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey('warehouses.Location', on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'parent_code']
        indexes = [
            models.Index(fields=['company', 'product']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"{self.parent_code} ({self.quantity} items)"


class AggregationItem(models.Model):
    """Child items in an aggregation"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    aggregation = models.ForeignKey(Aggregation, on_delete=models.CASCADE, related_name='items')
    marking_code = models.ForeignKey(MarkingCode, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['aggregation', 'marking_code']
        indexes = [models.Index(fields=['company', 'aggregation'])]

    def __str__(self):
        return f"{self.marking_code.code} in {self.aggregation.parent_code}"


class CodeValidation(models.Model):
    """Record of every code validation attempt"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    code_input = models.CharField(max_length=200)
    code_type = models.CharField(max_length=20, choices=[
        ('gtin', 'GTIN'),
        ('barcode', 'Barcode'),
        ('marking', 'Marking Code'),
        ('serial', 'Serial Number'),
    ])
    result = models.CharField(max_length=20, choices=[
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('unknown', 'Unknown'),
        ('already_sold', 'Already Sold'),
        ('already_used', 'Already Used'),
        ('wrong_product', 'Wrong Product'),
        ('wrong_company', 'Wrong Company'),
        ('wrong_warehouse', 'Wrong Warehouse'),
        ('expired', 'Expired'),
    ])
    resolved_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    marking_code = models.ForeignKey(MarkingCode, on_delete=models.SET_NULL, null=True, blank=True)
    gtin = models.ForeignKey(GTIN, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    verified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['company', 'code_input']),
            models.Index(fields=['company', 'result']),
            models.Index(fields=['code_input']),
        ]

    def __str__(self):
        return f"{self.code_input} → {self.get_result_display()}"
