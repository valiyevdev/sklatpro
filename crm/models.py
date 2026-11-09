from django.db import models
from django.conf import settings
from users.models import Company


class CustomerSegment(models.Model):
    """Customer segmentation — VIP, Wholesale, Retail, etc."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_segments')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#6366f1')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'slug']

    def __str__(self):
        return self.name


class CustomerTag(models.Model):
    """Customer tags — reusable labels."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6b7280')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'name']

    def __str__(self):
        return self.name


class CustomerSegmentAssignment(models.Model):
    """Many-to-many with extra data for segment assignment."""
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='segment_assignments')
    segment = models.ForeignKey(CustomerSegment, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['customer', 'segment']

    def __str__(self):
        return f"{self.customer.name} → {self.segment.name}"


class CustomerTagAssignment(models.Model):
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(CustomerTag, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['customer', 'tag']

    def __str__(self):
        return f"{self.customer.name} → {self.tag.name}"


class CustomerCommunication(models.Model):
    """Communication log — calls, emails, meetings, etc."""
    CHANNEL_CHOICES = [
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('meeting', 'Meeting'),
        ('other', 'Other'),
    ]
    TYPE_CHOICES = [
        ('call', 'Call'),
        ('email', 'Email'),
        ('message', 'Message'),
        ('meeting', 'Meeting'),
        ('note', 'Note'),
        ('follow_up', 'Follow Up'),
    ]
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_communications')
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='communications')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='phone')
    comm_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='call')
    subject = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    direction = models.CharField(max_length=10, choices=[('outbound', 'Outbound'), ('inbound', 'Inbound')], default='outbound')
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='comm_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_comm_type_display()} - {self.customer.name} ({self.created_at:%d.%m.%Y})"


class CustomerNote(models.Model):
    """Internal customer notes."""
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('finance', 'Finance'),
        ('sales', 'Sales'),
        ('support', 'Support'),
        ('warning', 'Warning'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_notes')
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='crm_notes')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    is_important = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note: {self.customer.name} - {self.title or self.content[:50]}"


class CustomerDocument(models.Model):
    """Customer documents — contracts, invoices, etc."""
    CATEGORY_CHOICES = [
        ('contract', 'Contract'),
        ('invoice', 'Invoice'),
        ('id', 'ID Document'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_documents')
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='documents')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='customer_documents/%Y/%m/', blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.customer.name}"


class CustomerTask(models.Model):
    """CRM tasks linked to customers."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    TYPE_CHOICES = [
        ('call', 'Call Customer'),
        ('follow_up', 'Follow Up'),
        ('send_invoice', 'Send Invoice'),
        ('collect_payment', 'Collect Payment'),
        ('prepare_offer', 'Prepare Offer'),
        ('meeting', 'Meeting'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_tasks')
    customer = models.ForeignKey('sales.Customer', on_delete=models.CASCADE, related_name='crm_tasks')
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_crm_tasks')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_crm_tasks')
    related_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    related_sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-priority']
        verbose_name_plural = 'Customer tasks'

    def __str__(self):
        return f"{self.title} - {self.customer.name}"

    @property
    def is_overdue(self):
        if self.due_date and self.status != 'completed':
            from django.utils import timezone
            return self.due_date < timezone.now().date()
        return False
