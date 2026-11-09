from django.db import models
from django.conf import settings
from users.models import Company


class Notification(models.Model):
    TYPE_CHOICES = [
        ('low_stock', 'Low Stock'),
        ('new_order', 'New Order'),
        ('purchase_received', 'Purchase Received'),
        ('sale_completed', 'Sale Completed'),
        ('transfer_completed', 'Transfer Completed'),
        ('payment_overdue', 'Payment Overdue'),
        ('supplier_payment_due', 'Supplier Payment Due'),
        ('task_assigned', 'Task Assigned'),
        ('task_due_soon', 'Task Due Soon'),
        ('task_overdue', 'Task Overdue'),
        ('task_completed', 'Task Completed'),
        ('task_comment', 'Task Comment'),
        ('system', 'System Alert'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='system')
    read = models.BooleanField(default=False)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['user']),
            models.Index(fields=['read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.title
