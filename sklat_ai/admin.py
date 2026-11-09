from django.contrib import admin
from .models import (
    AIProviderConfig, AIConversation, AIMessage, AIInsight,
    AIForecast, AIBusinessHealth, AIRecommendation, AIUsageLog, AIFeedback,
)


@admin.register(AIProviderConfig)
class AIProviderConfigAdmin(admin.ModelAdmin):
    list_display = ['provider', 'model_name', 'company', 'is_active', 'monthly_budget_usd']
    list_filter = ['provider', 'is_active']


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'company', 'message_count', 'created_at']


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ['role', 'content', 'tokens_used', 'created_at']


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ['title', 'insight_type', 'priority', 'confidence', 'created_at']
    list_filter = ['insight_type', 'priority']


@admin.register(AIForecast)
class AIForecastAdmin(admin.ModelAdmin):
    list_display = ['product', 'horizon', 'predicted_demand', 'confidence', 'forecast_date']


@admin.register(AIBusinessHealth)
class AIBusinessHealthAdmin(admin.ModelAdmin):
    list_display = ['overall_score', 'overall_status', 'created_at']


@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'priority', 'confidence']
    list_filter = ['category', 'status', 'priority']


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ['feature', 'user', 'tokens_input', 'tokens_output', 'estimated_cost_usd', 'created_at']
    list_filter = ['feature', 'success']


@admin.register(AIFeedback)
class AIFeedbackAdmin(admin.ModelAdmin):
    list_display = ['rating', 'user', 'created_at']
