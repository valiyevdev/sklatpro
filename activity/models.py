from django.conf import settings

from django.db import models

from django.utils import timezone

from users.models import Company



class Activity(models.Model):

    ACTIVITY_TYPES = [

        ('product_added', 'Mahsulot qo\'shildi'),

        ('product_updated', 'Mahsulot yangilandi'),

        ('product_deleted', 'Mahsulot o\'chirildi'),

        ('stock_in', 'Mahsulot keldi'),

        ('stock_out', 'Mahsulot ketdi'),

        ('customer_debt_created', 'Mijoz qarzi yaratildi'),

        ('customer_debt_updated', 'Mijoz qarzi yangilandi'),

        ('customer_debt_paid', 'Mijoz qarzi to\'landi'),

        ('supplier_debt_created', 'Taminotchi qarzi yaratildi'),

        ('supplier_debt_updated', 'Taminotchi qarzi yangilandi'),

        ('supplier_debt_paid', 'Taminotchi qarzi to\'landi'),

        ('user_login', 'Foydalanuvchi kirdi'),

        ('user_logout', 'Foydalanuvchi chiqdi'),

        ('employee_created', 'Xodim yaratildi'),

        ('employee_updated', 'Xodim yangilandi'),

        ('employee_deleted', 'Xodim o\'chirildi'),

        ('task_created', 'Task Created'),
        ('task_assigned', 'Task Assigned'),
        ('task_completed', 'Task Completed'),
        ('task_status_changed', 'Task Status Changed'),
        ('task_priority_changed', 'Task Priority Changed'),
        ('task_due_date_changed', 'Task Due Date Changed'),
        ('task_comment_added', 'Task Comment Added'),
        ('task_deleted', 'Task Deleted'),
        ('checklist_item_added', 'Checklist Item Added'),
        ('checklist_item_completed', 'Checklist Item Completed'),
        ('checklist_item_uncompleted', 'Checklist Item Uncompleted'),

    ]

    

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_activities', null=True, blank=True, verbose_name="Company")

    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES, verbose_name="Faoliyat turi")

    description = models.TextField(verbose_name="Tavsif")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='activities', verbose_name="Foydalanuvchi")

    related_object_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="Bog'liq obyekt turi")

    related_object_id = models.PositiveIntegerField(blank=True, null=True, verbose_name="Bog'liq obyekt ID")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    

    class Meta:

        ordering = ['-created_at']

        verbose_name = "Faoliyat"

        verbose_name_plural = "Faoliyatlar"

        indexes = [

            models.Index(fields=['company']),

            models.Index(fields=['user']),

            models.Index(fields=['activity_type']),

            models.Index(fields=['created_at']),

        ]

    

    def __str__(self):

        return f"{self.get_activity_type_display()} - {self.user.username if self.user else 'System'}"

    

    @classmethod
    def log_activity(cls, activity_type, description, user=None, company=None, related_object_type=None, related_object_id=None):
        if company is None and user and hasattr(user, 'company'):
            company = user.company
        return cls.objects.create(
            activity_type=activity_type,
            description=description,
            user=user,
            company=company,
            related_object_type=related_object_type,
            related_object_id=related_object_id
        )



