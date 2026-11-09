import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class AIProviderConfig(models.Model):
    """AI provider configuration per company."""
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('local', 'Local Model'),
        ('custom', 'Custom API'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_configs')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=100, default='gpt-4o-mini')
    api_key_encrypted = models.TextField(blank=True, help_text='Encrypted API key - stored via IntegrationCredential')
    api_base_url = models.URLField(blank=True, default='https://api.openai.com/v1')
    temperature = models.FloatField(default=0.3)
    max_tokens = models.PositiveIntegerField(default=2000)
    timeout_seconds = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    enabled_features = models.JSONField(default=dict, blank=True)
    monthly_budget_usd = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'provider']

    def __str__(self):
        return f"{self.get_provider_display()} - {self.company}"


class AIConversation(models.Model):
    """AI conversation session."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_conversations')
    title = models.CharField(max_length=200, blank=True)
    context_module = models.CharField(max_length=100, blank=True)
    context_object_type = models.CharField(max_length=100, blank=True)
    context_object_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    message_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat: {self.title or 'New'} ({self.user})"


class AIMessage(models.Model):
    """Individual message in an AI conversation."""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class AIInsight(models.Model):
    """AI-generated business insight."""
    TYPE_CHOICES = [
        ('anomaly', 'Anomaly'),
        ('recommendation', 'Recommendation'),
        ('forecast', 'Forecast'),
        ('summary', 'Summary'),
        ('alert', 'Alert'),
        ('opportunity', 'Opportunity'),
        ('risk', 'Risk'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_insights')
    insight_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    description = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    related_module = models.CharField(max_length=100, blank=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    related_object_id = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(default=0.0)
    data_period_start = models.DateField(null=True, blank=True)
    data_period_end = models.DateField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    is_actioned = models.BooleanField(default=False)
    action_taken = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'insight_type']),
            models.Index(fields=['company', 'priority']),
        ]

    def __str__(self):
        return f"[{self.get_insight_type_display()}] {self.title}"


class AIForecast(models.Model):
    """AI demand/sales forecast for a product."""
    HORIZON_CHOICES = [
        ('7d', '7 Days'),
        ('14d', '14 Days'),
        ('30d', '30 Days'),
        ('60d', '60 Days'),
        ('90d', '90 Days'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_forecasts')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='ai_forecasts')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, null=True, blank=True, related_name='ai_forecasts')
    horizon = models.CharField(max_length=10, choices=HORIZON_CHOICES)
    predicted_demand = models.DecimalField(max_digits=12, decimal_places=2)
    confidence = models.FloatField(default=0.0)
    data_days_used = models.PositiveIntegerField(default=0)
    method = models.CharField(max_length=50, blank=True)
    avg_daily_demand = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trend = models.CharField(max_length=20, default='stable')
    days_until_stockout = models.PositiveIntegerField(null=True, blank=True)
    recommended_order_qty = models.PositiveIntegerField(null=True, blank=True)
    forecast_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'product']),
            models.Index(fields=['company', 'forecast_date']),
        ]

    def __str__(self):
        return f"Forecast: {self.product} ({self.horizon})"


class AIBusinessHealth(models.Model):
    """Overall business health score snapshot."""
    SCORE_CHOICES = [
        ('healthy', 'Healthy'),
        ('watch', 'Watch'),
        ('critical', 'Critical'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_health_scores')
    overall_score = models.FloatField(default=0.0)
    overall_status = models.CharField(max_length=20, choices=SCORE_CHOICES, default='healthy')
    sales_score = models.FloatField(default=0.0)
    inventory_score = models.FloatField(default=0.0)
    finance_score = models.FloatField(default=0.0)
    customer_score = models.FloatField(default=0.0)
    operations_score = models.FloatField(default=0.0)
    logistics_score = models.FloatField(default=0.0)
    dimension_details = models.JSONField(default=dict, blank=True)
    recommendations_count = models.PositiveIntegerField(default=0)
    critical_alerts_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Health: {self.overall_score:.0f} ({self.overall_status})"


class AIRecommendation(models.Model):
    """Specific AI recommendation with action proposal."""
    CATEGORY_CHOICES = [
        ('restock', 'Restock'),
        ('pricing', 'Pricing'),
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
        ('operations', 'Operations'),
        ('finance', 'Finance'),
        ('marketing', 'Marketing'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('accepted', 'Accepted'),
        ('dismissed', 'Dismissed'),
        ('expired', 'Expired'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_recommendations')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium')
    title = models.CharField(max_length=200)
    description = models.TextField()
    impact = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    action_type = models.CharField(max_length=100, blank=True)
    action_config = models.JSONField(default=dict, blank=True)
    related_module = models.CharField(max_length=100, blank=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    related_object_id = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(default=0.0)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    action_taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    action_taken_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'category']),
        ]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"


class AIUsageLog(models.Model):
    """Track AI usage for cost monitoring."""
    FEATURE_CHOICES = [
        ('chat', 'Chat'),
        ('summary', 'Summary'),
        ('forecast', 'Forecast'),
        ('anomaly', 'Anomaly Detection'),
        ('recommendation', 'Recommendation'),
        ('analysis', 'Analysis'),
        ('report', 'Report Generation'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_usage_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='ai_usage_logs')
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    provider = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=100, blank=True)
    tokens_input = models.PositiveIntegerField(default=0)
    tokens_output = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    response_time_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'feature']),
        ]

    def __str__(self):
        return f"{self.feature} - {self.user} ({self.created_at})"


class AIFeedback(models.Model):
    """User feedback on AI responses."""
    RATING_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
        ('incorrect', 'Incorrect'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='ai_feedbacks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_feedbacks')
    message = models.ForeignKey(AIMessage, on_delete=models.CASCADE, related_name='feedbacks')
    rating = models.CharField(max_length=20, choices=RATING_CHOICES)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating} - {self.message}"
