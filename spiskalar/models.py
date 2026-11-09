from django.db import models
from django.conf import settings
from users.models import Company
from django.utils import timezone


class SpiskalarList(models.Model):
    TYPE_CHOICES = [
        ('picking', 'Picking List'),
        ('packing', 'Packing List'),
        ('shipping', 'Shipping List'),
        ('restock', 'Restock List'),
        ('inventory_count', 'Inventory Count'),
        ('purchase', 'Purchase List'),
        ('transfer', 'Transfer List'),
        ('delivery', 'Delivery List'),
        ('customer_followup', 'Customer Follow-up'),
        ('custom', 'Custom List'),
    ]
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
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='spiskalar_lists')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='custom')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_lists')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_lists')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'List'
        verbose_name_plural = 'Lists'
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return self.name

    @property
    def progress(self):
        total = self.items.count()
        if total == 0:
            return 0
        completed = self.items.filter(completed=True).count()
        return round((completed / total) * 100)

    @property
    def progress_display(self):
        total = self.items.count()
        completed = self.items.filter(completed=True).count()
        return f"{completed}/{total}"

    @property
    def is_overdue(self):
        if self.due_date and self.status != 'completed':
            return timezone.now().date() > self.due_date
        return False

    @property
    def related_object_label(self):
        return self.type.replace('_', ' ').title()


class SpiskalarItem(models.Model):
    list = models.ForeignKey(SpiskalarList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    completed_quantity = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        if self.product:
            return f"{self.product.name} x {self.quantity}"
        return self.title or f"Item x {self.quantity}"

    @property
    def is_fully_completed(self):
        return self.completed_quantity >= self.quantity

    @property
    def display_name(self):
        return self.product.name if self.product else self.title


class Task(models.Model):
    TYPE_CHOICES = [
        ('operational', 'Operational Task'),
        ('warehouse', 'Warehouse Task'),
        ('sales', 'Sales Task'),
        ('customer', 'Customer Task'),
        ('finance', 'Finance Task'),
        ('administrative', 'Administrative Task'),
        ('custom', 'Custom Task'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('backlog', 'Backlog'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting'),
        ('blocked', 'Blocked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='custom')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_assignments')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_tasks')
    spiskalar_list = models.ForeignKey(SpiskalarList, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_tasks')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['task_type']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return self.title

    @property
    def progress(self):
        items = self.checklist_items.all()
        total = items.count()
        if total == 0:
            return 0 if self.status not in ('completed',) else 100
        done = items.filter(completed=True).count()
        return round((done / total) * 100)

    @property
    def progress_display(self):
        items = self.checklist_items.all()
        total = items.count()
        done = items.filter(completed=True).count()
        return f"{done}/{total}"

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ('completed', 'cancelled'):
            return timezone.now().date() > self.due_date
        return False

    @property
    def days_until_due(self):
        if self.due_date:
            delta = self.due_date - timezone.now().date()
            return delta.days
        return None


class ChecklistItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    title = models.CharField(max_length=300)
    completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on {self.task}"


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename


class TaskTemplate(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='task_templates')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=Task.TYPE_CHOICES, default='custom')
    priority = models.CharField(max_length=10, choices=Task.PRIORITY_CHOICES, default='normal')
    checklist_items = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def create_task(self, company, created_by, assigned_to=None, due_date=None):
        task = Task.objects.create(
            company=company,
            title=self.name,
            description=self.description,
            task_type=self.task_type,
            priority=self.priority,
            created_by=created_by,
            assigned_to=assigned_to,
            assigned_by=created_by,
            due_date=due_date,
        )
        for idx, item_title in enumerate(self.checklist_items):
            if isinstance(item_title, str):
                ChecklistItem.objects.create(task=task, title=item_title, order=idx)
            elif isinstance(item_title, dict):
                ChecklistItem.objects.create(task=task, title=item_title.get('title', ''), order=idx)
        return task
