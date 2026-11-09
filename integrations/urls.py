from django.urls import path
from . import views

app_name = 'integrations'

urlpatterns = [
    path('', views.integrations_dashboard, name='dashboard'),
    path('list/', views.integration_list, name='integration_list'),
    path('providers/', views.provider_list, name='provider_list'),
    path('connections/create/', views.connection_create, name='connection_create'),
    path('connections/<uuid:pk>/', views.connection_detail, name='connection_detail'),
    path('connections/<uuid:pk>/edit/', views.connection_edit, name='connection_edit'),
    path('connections/<uuid:pk>/toggle/', views.connection_toggle, name='connection_toggle'),
    path('connections/<uuid:pk>/test/', views.test_connection_view, name='test_connection'),
    path('sync/', views.sync_jobs_list, name='sync_jobs'),
    path('sync/<uuid:pk>/', views.sync_job_detail, name='sync_job_detail'),
    path('sync/<uuid:pk>/retry/', views.sync_job_retry, name='sync_job_retry'),
    path('sync/<uuid:pk>/cancel/', views.sync_job_cancel, name='sync_job_cancel'),
    path('webhooks/', views.webhook_list, name='webhook_list'),
    path('webhooks/create/', views.webhook_create, name='webhook_create'),
    path('webhooks/<uuid:pk>/', views.webhook_detail, name='webhook_detail'),
    path('webhooks/<uuid:pk>/toggle/', views.webhook_toggle, name='webhook_toggle'),
    path('webhooks/<uuid:pk>/events/', views.webhook_events, name='webhook_events'),
    path('api-keys/', views.api_key_list, name='api_key_list'),
    path('api-keys/create/', views.api_key_create, name='api_key_create'),
    path('api-keys/<uuid:pk>/revoke/', views.api_key_revoke, name='api_key_revoke'),
    path('logs/', views.integration_logs, name='logs'),
    path('errors/', views.integration_errors, name='errors'),
    path('mappings/', views.object_mappings, name='object_mappings'),
    path('circuit-breakers/', views.circuit_breaker_list, name='circuit_breakers'),
    path('events/', views.integration_events, name='events'),
]
