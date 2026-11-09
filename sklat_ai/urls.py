from django.urls import path
from . import views

app_name = 'sklat_ai'

urlpatterns = [
    path('', views.ai_dashboard, name='dashboard'),
    path('chat/', views.ai_chat, name='chat'),
    path('chat/<uuid:conversation_id>/', views.ai_chat, name='chat_conversation'),
    path('conversations/', views.ai_conversation_list, name='conversation_list'),
    path('conversations/<uuid:conversation_id>/', views.ai_conversation_detail, name='conversation_detail'),
    path('insights/', views.ai_insights, name='insights'),
    path('insights/<uuid:insight_id>/', views.ai_insight_detail, name='insight_detail'),
    path('forecasts/', views.ai_forecasts, name='forecasts'),
    path('recommendations/', views.ai_recommendations, name='recommendations'),
    path('action-center/', views.ai_action_center, name='action_center'),
    path('summary/', views.ai_business_summary, name='business_summary'),
    path('anomalies/', views.ai_anomalies, name='anomalies'),
    path('analytics/', views.ai_analytics, name='analytics'),
    path('config/', views.ai_config, name='config'),
    path('feedback/', views.ai_feedback, name='feedback'),
    path('generate-insight/', views.ai_generate_insight, name='generate_insight'),
    path('execute-action/', views.ai_execute_action, name='execute_action'),
    path('execute-action/<uuid:rec_id>/', views.ai_execute_action, name='execute_action_detail'),
    path('dismiss/', views.ai_dismiss_recommendation, name='dismiss_recommendation'),
    path('dismiss/<uuid:rec_id>/', views.ai_dismiss_recommendation, name='dismiss_recommendation_detail'),
    path('create-draft/', views.ai_execute_action, name='create_draft'),
    path('export/summary/', views.ai_export_summary, name='export_summary'),
    path('export/analytics/', views.ai_export_analytics, name='export_analytics'),
    path('forecast-evaluate/', views.ai_forecast_evaluate, name='forecast_evaluate'),
    path('prune-conversations/', views.ai_prune_conversations, name='prune_conversations'),
    path('validate-response/', views.ai_validate_response, name='validate_response'),
    path('auto-insights/', views.ai_generate_insight, name='auto_insights'),
]
