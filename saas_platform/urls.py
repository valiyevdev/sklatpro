from django.urls import path
from . import views

app_name = 'saas_platform'

urlpatterns = [
    path('', views.platform_dashboard, name='dashboard'),
    path('companies/', views.company_list, name='company_list'),
    path('companies/<uuid:company_id>/', views.company_detail, name='company_detail'),
    path('companies/<uuid:company_id>/toggle/', views.company_toggle, name='company_toggle'),
    path('companies/<uuid:company_id>/set-plan/', views.company_set_plan, name='company_set_plan'),
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('plans/create/', views.plan_create, name='plan_create'),
    path('plans/<uuid:plan_id>/update/', views.plan_update, name='plan_update'),
    path('users/', views.user_list, name='user_list'),
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('audit/', views.audit_log_view, name='audit_log'),
    path('audit/export/', views.audit_export, name='audit_export'),
    path('flags/', views.feature_flags, name='feature_flags'),
    path('flags/create/', views.flag_create, name='flag_create'),
    path('flags/<uuid:flag_id>/toggle/', views.flag_toggle, name='flag_toggle'),
    path('health/', views.health_check_api, name='health_check'),
]
