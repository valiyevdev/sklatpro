from django.db import models
from django.utils import timezone
import uuid


class Document(models.Model):
    """Centralized document model"""
    TYPE_CHOICES = [
        ('sales_invoice', 'Sales Invoice'),
        ('purchase_invoice', 'Purchase Invoice'),
        ('proforma_invoice', 'Proforma Invoice'),
        ('credit_note', 'Credit Note'),
        ('debit_note', 'Debit Note'),
        ('delivery_note', 'Delivery Note'),
        ('goods_receipt', 'Goods Receipt'),
        ('goods_issue', 'Goods Issue'),
        ('return_document', 'Return Document'),
        ('payment_receipt', 'Payment Receipt'),
        ('contract', 'Contract'),
        ('commercial_offer', 'Commercial Offer'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    number = models.CharField(max_length=50)
    title = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    
    customer = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_documents')
    supplier = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='supplier_documents')
    
    currency = models.CharField(max_length=3, default='UZS')
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Links to business objects
    reference_type = models.CharField(max_length=50, blank=True, null=True)  # sale, purchase, order, etc.
    reference_id = models.IntegerField(blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)
    
    # Electronic document / EDO fields
    is_electronic = models.BooleanField(default=False)
    external_id = models.CharField(max_length=200, blank=True, null=True)
    external_status = models.CharField(max_length=30, choices=[
        ('not_submitted', 'Not Submitted'),
        ('submitting', 'Submitting'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('error', 'Error'),
    ], default='not_submitted')
    external_response = models.TextField(blank=True, null=True)
    external_submitted_at = models.DateTimeField(blank=True, null=True)
    
    # Signature fields
    signature_status = models.CharField(max_length=20, choices=[
        ('unsigned', 'Unsigned'),
        ('pending', 'Pending Signature'),
        ('signed', 'Signed'),
        ('rejected', 'Rejected'),
    ], default='unsigned')
    signed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_documents')
    signed_at = models.DateTimeField(blank=True, null=True)
    external_signature_id = models.CharField(max_length=200, blank=True, null=True)
    
    # Approval workflow
    approval_status = models.CharField(max_length=20, choices=[
        ('none', 'No Approval Required'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='none')
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_documents')
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Versioning
    version = models.PositiveIntegerField(default=1)
    parent_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_versions')
    version_reason = models.CharField(max_length=200, blank=True, null=True)
    
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='created_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['company', 'number']
        indexes = [
            models.Index(fields=['company', 'doc_type']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'date']),
            models.Index(fields=['company', 'customer']),
            models.Index(fields=['company', 'supplier']),
            models.Index(fields=['company', 'number']),
            models.Index(fields=['company', 'external_status']),
        ]
    
    def __str__(self):
        return f"{self.get_doc_type_display()} {self.number}"


class DocumentItem(models.Model):
    """Line items within a document"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=300, blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Traceability links
    gtin = models.CharField(max_length=14, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    marking_code = models.CharField(max_length=200, blank=True, null=True)
    
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'id']
        indexes = [models.Index(fields=['company', 'document'])]
    
    def __str__(self):
        return f"{self.description or self.product} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.line_total = (self.quantity * self.unit_price) - self.discount + self.tax
        super().save(*args, **kwargs)


class DocumentAttachment(models.Model):
    """File attachments for documents"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='document_attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    uploaded_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [models.Index(fields=['company', 'document'])]
    
    def __str__(self):
        return self.filename


class DocumentVersion(models.Model):
    """Document version history"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reason = models.CharField(max_length=200, blank=True, null=True)
    snapshot = models.JSONField(default=dict, blank=True)  # Full snapshot of document data
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']
        indexes = [models.Index(fields=['company', 'document'])]
    
    def __str__(self):
        return f"{self.document.number} v{self.version_number}"


class DocumentTemplate(models.Model):
    """Reusable document templates"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    doc_type = models.CharField(max_length=30, choices=Document.TYPE_CHOICES)
    template_html = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [models.Index(fields=['company', 'doc_type'])]
    
    def __str__(self):
        return f"{self.name} ({self.get_doc_type_display()})"


class DocumentSignature(models.Model):
    """Document electronic signature records"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='signatures')
    signer = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('signed', 'Signed'),
        ('rejected', 'Rejected'),
    ], default='pending')
    external_signature_id = models.CharField(max_length=200, blank=True, null=True)
    certificate_info = models.JSONField(default=dict, blank=True)
    signed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'document'])]
    
    def __str__(self):
        return f"Signature for {self.document.number} by {self.signer}"


class EDOConfig(models.Model):
    """EDO (Electronic Document Exchange) provider configuration"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=100)
    provider_code = models.CharField(max_length=50)  # e.g., 'texnopark_edo', 'custom'
    is_active = models.BooleanField(default=False)
    api_url = models.URLField(blank=True, null=True)
    api_key = models.CharField(max_length=500, blank=True, null=True)  # Encrypted in production
    config_json = models.JSONField(default=dict, blank=True)
    last_request_at = models.DateTimeField(blank=True, null=True)
    last_status = models.CharField(max_length=50, blank=True, null=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'EDO Configuration'
        verbose_name_plural = 'EDO Configurations'
        indexes = [models.Index(fields=['company', 'provider_code'])]
    
    def __str__(self):
        return f"{self.provider_name} ({'Active' if self.is_active else 'Inactive'})"


class EDOTransaction(models.Model):
    """Track every EDO request/response"""
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    config = models.ForeignKey(EDOConfig, on_delete=models.CASCADE, related_name='transactions')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='edo_transactions')
    direction = models.CharField(max_length=10, choices=[('out', 'Outbound'), ('in', 'Inbound')])
    action = models.CharField(max_length=50)  # send, status_check, download, cancel
    external_id = models.CharField(max_length=200, blank=True, null=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ], default='pending')
    error_code = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, editable=False)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'document']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['idempotency_key']),
        ]
    
    def __str__(self):
        return f"{self.action} for {self.document.number} ({self.status})"
