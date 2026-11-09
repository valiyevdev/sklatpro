import uuid
import json
from django.db import models
from django.conf import settings
from django.utils import timezone


class AutomationRule(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('disabled', 'Disabled'),
        ('error', 'Error'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='automation_rules')
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    trigger_type = models.CharField(max_length=50)
    trigger_config = models.JSONField(default=dict, blank=True)
    conditions = models.JSONField(default=dict, blank=True,
        help_text='JSON condition tree: {"logic": "all", "items": [...]}')
    actions = models.JSONField(default=list, blank=True,
        help_text='List of action configs: [{"type": "...", "config": {...}}]')
    conditions_logic = models.CharField(max_length=10, choices=[('all', 'ALL'), ('any', 'ANY')], default='all')
    schedule_type = models.CharField(max_length=20, choices=[
        ('', 'Event-based'), ('daily', 'Daily'), ('weekly', 'Weekly'),
        ('monthly', 'Monthly'), ('interval', 'Interval'), ('cron', 'Cron'),
    ], blank=True, default='')
    schedule_config = models.JSONField(default=dict, blank=True)
    max_execution_depth = models.PositiveIntegerField(default=5)
    rate_limit_per_hour = models.PositiveIntegerField(default=100)
    is_template = models.BooleanField(default=False)
    template_name = models.CharField(max_length=200, blank=True)
    version = models.PositiveIntegerField(default=1)
    version_history = models.JSONField(default=list, blank=True)
    last_executed = models.DateTimeField(null=True, blank=True)
    execution_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    health_status = models.CharField(max_length=20, default='healthy')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['trigger_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def human_readable(self):
        parts = []
        trigger_display = self.get_trigger_display()
        parts.append(f"WHEN: {trigger_display}")
        if self.conditions and self.conditions.get('items'):
            logic = self.conditions_logic.upper()
            cond_str = f"IF ({logic}): conditions present"
            parts.append(cond_str)
        if self.actions:
            action_count = len(self.actions)
            parts.append(f"THEN: {action_count} action(s)")
        return " | ".join(parts)

    def get_trigger_display(self):
        return TRIGGER_CHOICES_MAP.get(self.trigger_type, self.trigger_type)


class AutomationExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='executions')
    event_id = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='automation_executions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    actions_total = models.PositiveIntegerField(default=0)
    actions_succeeded = models.PositiveIntegerField(default=0)
    actions_failed = models.PositiveIntegerField(default=0)
    actions_skipped = models.PositiveIntegerField(default=0)
    conditions_matched = models.BooleanField(default=False)
    result_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    action_results = models.JSONField(default=list, blank=True)
    execution_depth = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    dry_run = models.BooleanField(default=False)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['rule', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"{self.rule.name} - {self.get_status_display()} ({self.created_at})"


class AutomationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='automation_events')
    event_type = models.CharField(max_length=100, db_index=True)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict)
    source = models.CharField(max_length=100, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_depth = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'event_type']),
            models.Index(fields=['processed', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"


class AutomationSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.OneToOneField(AutomationRule, on_delete=models.CASCADE, related_name='schedule')
    schedule_type = models.CharField(max_length=20)
    config = models.JSONField(default=dict)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Schedule for {self.rule.name} ({self.schedule_type})"


# ============================================================
# TRIGGER TYPE DEFINITIONS
# ============================================================
TRIGGER_CATEGORIES = {
    'product': {
        'label': 'Product',
        'icon': 'bi-box',
        'triggers': [
            ('product.created', 'Product Created'),
            ('product.updated', 'Product Updated'),
            ('product.activated', 'Product Activated'),
            ('product.deactivated', 'Product Deactivated'),
            ('product.price_changed', 'Product Price Changed'),
        ],
    },
    'inventory': {
        'label': 'Inventory',
        'icon': 'bi-archive',
        'triggers': [
            ('inventory.stock_increased', 'Stock Increased'),
            ('inventory.stock_decreased', 'Stock Decreased'),
            ('inventory.stock_below_minimum', 'Stock Below Minimum'),
            ('inventory.stock_above_maximum', 'Stock Above Maximum'),
            ('inventory.product_out_of_stock', 'Product Out of Stock'),
            ('inventory.product_back_in_stock', 'Product Back in Stock'),
            ('inventory.adjustment_created', 'Inventory Adjustment Created'),
            ('inventory.batch_near_expiry', 'Batch Near Expiry'),
            ('inventory.batch_expired', 'Batch Expired'),
        ],
    },
    'purchase': {
        'label': 'Purchase',
        'icon': 'bi-cart-plus',
        'triggers': [
            ('purchase.created', 'Purchase Created'),
            ('purchase.approved', 'Purchase Approved'),
            ('purchase.received', 'Purchase Received'),
            ('purchase.overdue', 'Purchase Overdue'),
            ('purchase.supplier_payment_due', 'Supplier Payment Due'),
        ],
    },
    'sales': {
        'label': 'Sales',
        'icon': 'bi-currency-dollar',
        'triggers': [
            ('sale.created', 'Sale Created'),
            ('sale.confirmed', 'Sale Confirmed'),
            ('sale.completed', 'Sale Completed'),
            ('sale.cancelled', 'Sale Cancelled'),
            ('sale.returned', 'Sale Returned'),
            ('sale.payment_received', 'Payment Received'),
            ('sale.payment_overdue', 'Sale Payment Overdue'),
        ],
    },
    'order': {
        'label': 'Order',
        'icon': 'bi-receipt',
        'triggers': [
            ('order.created', 'Order Created'),
            ('order.confirmed', 'Order Confirmed'),
            ('order.reserved', 'Order Reserved'),
            ('order.picking_started', 'Order Picking Started'),
            ('order.picked', 'Order Picked'),
            ('order.packed', 'Order Packed'),
            ('order.shipped', 'Order Shipped'),
            ('order.delivered', 'Order Delivered'),
            ('order.cancelled', 'Order Cancelled'),
            ('order.completed', 'Order Completed'),
        ],
    },
    'crm': {
        'label': 'CRM',
        'icon': 'bi-people',
        'triggers': [
            ('customer.created', 'Customer Created'),
            ('customer.updated', 'Customer Updated'),
            ('customer.segment_changed', 'Customer Segment Changed'),
            ('customer.became_vip', 'Customer Became VIP'),
            ('customer.debt_overdue', 'Customer Debt Overdue'),
            ('customer.inactive', 'Customer Inactive'),
        ],
    },
    'finance': {
        'label': 'Finance',
        'icon': 'bi-bank',
        'triggers': [
            ('payment.created', 'Payment Created'),
            ('payment.completed', 'Payment Completed'),
            ('payment.failed', 'Payment Failed'),
            ('expense.created', 'Expense Created'),
            ('receivable_overdue', 'Receivable Overdue'),
            ('budget_exceeded', 'Budget Exceeded'),
            ('cash_balance_below', 'Cash Balance Below Threshold'),
        ],
    },
    'pos': {
        'label': 'POS',
        'icon': 'bi-display',
        'triggers': [
            ('pos.sale_completed', 'POS Sale Completed'),
            ('pos.shift_opened', 'Shift Opened'),
            ('pos.shift_closed', 'Shift Closed'),
            ('pos.refund_created', 'Refund Created'),
            ('pos.large_discount_applied', 'Large Discount Applied'),
        ],
    },
    'wms': {
        'label': 'WMS',
        'icon': 'bi-building',
        'triggers': [
            ('wms.receiving_completed', 'Receiving Completed'),
            ('wms.picking_created', 'Picking Created'),
            ('wms.picking_completed', 'Picking Completed'),
            ('wms.packing_completed', 'Packing Completed'),
            ('wms.shipment_ready', 'Shipment Ready'),
            ('wms.transfer_created', 'Transfer Created'),
            ('wms.transfer_received', 'Transfer Received'),
        ],
    },
    'logistics': {
        'label': 'Logistics',
        'icon': 'bi-truck',
        'triggers': [
            ('logistics.shipment_created', 'Shipment Created'),
            ('logistics.shipment_dispatched', 'Shipment Dispatched'),
            ('logistics.delivery_completed', 'Delivery Completed'),
            ('logistics.delivery_failed', 'Delivery Failed'),
            ('logistics.delivery_rescheduled', 'Delivery Rescheduled'),
        ],
    },
    'document': {
        'label': 'Document',
        'icon': 'bi-file-earmark',
        'triggers': [
            ('document.created', 'Document Created'),
            ('document.approved', 'Document Approved'),
            ('document.rejected', 'Document Rejected'),
            ('document.sent', 'Document Sent'),
            ('document.signature_completed', 'Signature Completed'),
        ],
    },
    'ecommerce': {
        'label': 'E-Commerce',
        'icon': 'bi-broadcast',
        'triggers': [
            ('ecommerce.online_order_created', 'Online Order Created'),
            ('ecommerce.online_payment_completed', 'Online Payment Completed'),
            ('ecommerce.cart_abandoned', 'Cart Abandoned'),
            ('ecommerce.stock_sync_failed', 'Stock Sync Failed'),
            ('ecommerce.marketplace_order_imported', 'Marketplace Order Imported'),
        ],
    },
    'integration': {
        'label': 'Integration',
        'icon': 'bi-plug',
        'triggers': [
            ('integration.webhook_received', 'Webhook Received'),
            ('integration.sync_completed', 'Sync Completed'),
            ('integration.sync_failed', 'Sync Failed'),
            ('integration.disconnected', 'Integration Disconnected'),
            ('integration.auth_expired', 'Authentication Expired'),
        ],
    },
    'task': {
        'label': 'Task',
        'icon': 'bi-list-check',
        'triggers': [
            ('task.created', 'Task Created'),
            ('task.assigned', 'Task Assigned'),
            ('task.due_soon', 'Task Due Soon'),
            ('task.overdue', 'Task Overdue'),
            ('task.completed', 'Task Completed'),
        ],
    },
    'schedule': {
        'label': 'Scheduled',
        'icon': 'bi-clock',
        'triggers': [
            ('schedule.daily', 'Every Day'),
            ('schedule.weekly', 'Every Week'),
            ('schedule.monthly', 'Every Month'),
            ('schedule.custom', 'Custom Schedule'),
        ],
    },
}

TRIGGER_CHOICES_MAP = {}
for cat_data in TRIGGER_CATEGORIES.values():
    for code, label in cat_data['triggers']:
        TRIGGER_CHOICES_MAP[code] = label

TRIGGER_CHOICES = [(code, label) for cat_data in TRIGGER_CATEGORIES.values() for code, label in cat_data['triggers']]


# ============================================================
# CONDITION OPERATORS
# ============================================================
OPERATOR_CHOICES = [
    ('equals', 'Equals'),
    ('not_equals', 'Not Equals'),
    ('gt', 'Greater Than'),
    ('gte', 'Greater Than or Equal'),
    ('lt', 'Less Than'),
    ('lte', 'Less Than or Equal'),
    ('contains', 'Contains'),
    ('not_contains', 'Does Not Contain'),
    ('starts_with', 'Starts With'),
    ('ends_with', 'Ends With'),
    ('in_list', 'In List'),
    ('not_in_list', 'Not In List'),
    ('between', 'Between'),
    ('is_empty', 'Is Empty'),
    ('is_not_empty', 'Is Not Empty'),
]


# ============================================================
# ACTION TYPES
# ============================================================
ACTION_TYPES = {
    'create_task': {
        'label': 'Vazifa yaratish',
        'icon': 'bi-list-check',
        'module': 'task',
        'config_fields': [
            {'name': 'title', 'label': 'Vazifa sarlavhasi', 'type': 'text', 'required': True, 'placeholder': 'Dinamik qiymatlar uchun {{variable}} dan foydalaning'},
            {'name': 'description', 'label': 'Tavsif', 'type': 'textarea', 'required': False},
            {'name': 'task_type', 'label': 'Vazifa turi', 'type': 'select', 'options': ['general', 'picking', 'packing', 'delivery', 'restock', 'follow_up', 'approval']},
            {'name': 'priority', 'label': 'Ustuvorlik', 'type': 'select', 'options': ['low', 'normal', 'high', 'urgent']},
            {'name': 'assigned_to_role', 'label': 'Tayinlash (rol)', 'type': 'select', 'options': ['warehouse_manager', 'account_manager', 'dispatcher', 'accountant', 'sales_manager']},
            {'name': 'due_in_days', 'label': 'Muddat (kun)', 'type': 'number', 'default': 1},
        ],
    },
    'send_notification': {
        'label': 'Bildirishnoma yuborish',
        'icon': 'bi-bell',
        'module': 'notification',
        'config_fields': [
            {'name': 'title', 'label': 'Bildirishnoma sarlavhasi', 'type': 'text', 'required': True},
            {'name': 'message', 'label': 'Xabar', 'type': 'textarea', 'required': True},
            {'name': 'notification_type', 'label': 'Turi', 'type': 'select', 'options': ['system', 'low_stock', 'new_order', 'payment_overdue', 'task_assigned']},
            {'name': 'notify_role', 'label': 'Xabardor qilish (rol)', 'type': 'select', 'options': ['company_admin', 'warehouse_manager', 'account_manager', 'dispatcher', 'accountant', 'sales_manager']},
        ],
    },
    'create_alert': {
        'label': 'Ogohlantirish yaratish',
        'icon': 'bi-exclamation-triangle',
        'module': 'notification',
        'config_fields': [
            {'name': 'title', 'label': 'Ogohlantirish sarlavhasi', 'type': 'text', 'required': True},
            {'name': 'message', 'label': 'Ogohlantirish xabari', 'type': 'textarea', 'required': True},
            {'name': 'severity', 'label': 'Jiddiylik', 'type': 'select', 'options': ['info', 'warning', 'danger']},
        ],
    },
    'add_comment': {
        'label': 'Izoh qo\'shish',
        'icon': 'bi-chat-dots',
        'module': 'task',
        'config_fields': [
            {'name': 'text', 'label': 'Izoh matni', 'type': 'textarea', 'required': True},
            {'name': 'object_type', 'label': 'Ob\'ekt turi', 'type': 'select', 'options': ['order', 'sale', 'purchase', 'customer', 'delivery']},
        ],
    },
    'update_order_status': {
        'label': 'Buyurtma holatini yangilash',
        'icon': 'bi-arrow-repeat',
        'module': 'order',
        'config_fields': [
            {'name': 'new_status', 'label': 'Yangi holat', 'type': 'select', 'options': ['confirmed', 'processing', 'shipped', 'delivered', 'completed', 'cancelled']},
        ],
    },
    'create_webhook': {
        'label': 'Webhook yuborish',
        'icon': 'bi-arrow-left-right',
        'module': 'integration',
        'config_fields': [
            {'name': 'event_type', 'label': 'Voqea turi', 'type': 'text', 'required': True},
            {'name': 'endpoint_id', 'label': 'Webhook Endpoint ID', 'type': 'text'},
        ],
    },
    'add_customer_tag': {
        'label': 'Mijoz tegini qo\'shish',
        'icon': 'bi-tag',
        'module': 'crm',
        'config_fields': [
            {'name': 'tag_name', 'label': 'Teg nomi', 'type': 'text', 'required': True},
        ],
    },
    'create_reminder': {
        'label': 'Eslatma yaratish',
        'icon': 'bi-alarm',
        'module': 'task',
        'config_fields': [
            {'name': 'title', 'label': 'Eslatma sarlavhasi', 'type': 'text', 'required': True},
            {'name': 'message', 'label': 'Xabar', 'type': 'textarea'},
            {'name': 'remind_in_days', 'label': 'Eslatma muddati (kun)', 'type': 'number', 'default': 1},
            {'name': 'assigned_to_role', 'label': 'Tayinlash (rol)', 'type': 'select', 'options': ['company_admin', 'warehouse_manager', 'account_manager', 'dispatcher', 'accountant']},
        ],
    },
    'update_product_field': {
        'label': 'Mahsulot maydonini yangilash',
        'icon': 'bi-pencil',
        'module': 'product',
        'config_fields': [
            {'name': 'field', 'label': 'Maydon', 'type': 'select', 'options': ['status', 'min_stock', 'notes']},
            {'name': 'value', 'label': 'Yangi qiymat', 'type': 'text', 'required': True},
        ],
    },
}

ACTION_TYPE_CHOICES = [(k, v['label']) for k, v in ACTION_TYPES.items()]
