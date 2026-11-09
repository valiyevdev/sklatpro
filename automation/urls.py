from django.urls import path
from . import views

app_name = 'automation'

urlpatterns = [
    path('', views.automation_dashboard, name='dashboard'),
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/create/', views.rule_create, name='rule_create'),
    path('rules/<uuid:pk>/', views.rule_detail, name='rule_detail'),
    path('rules/<uuid:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<uuid:pk>/toggle/', views.rule_toggle_status, name='rule_toggle'),
    path('rules/<uuid:pk>/delete/', views.rule_delete, name='rule_delete'),
    path('rules/<uuid:pk>/test/', views.rule_test, name='rule_test'),
    path('rules/<uuid:pk>/duplicate/', views.rule_duplicate, name='rule_duplicate'),
    path('rules/<uuid:pk>/versions/', views.rule_version_history, name='rule_versions'),
    path('executions/', views.execution_list, name='execution_list'),
    path('executions/<uuid:pk>/', views.execution_detail, name='execution_detail'),
    path('executions/<uuid:pk>/retry/', views.execution_retry, name='execution_retry'),
    path('logs/', views.automation_logs, name='logs'),
    path('templates/', views.automation_templates, name='templates'),
    path('analytics/', views.automation_analytics, name='analytics'),
]
