from django.urls import path
from . import views

app_name = 'ecommerce'

urlpatterns = [
    path('', views.ecommerce_dashboard, name='dashboard'),
    path('channels/', views.channel_list, name='channel_list'),
    path('channels/create/', views.channel_create, name='channel_create'),
    path('channels/<uuid:pk>/', views.channel_detail, name='channel_detail'),
    path('channels/<uuid:pk>/toggle/', views.channel_toggle, name='channel_toggle'),
    path('channels/<uuid:pk>/products/', views.channel_products_manage, name='channel_products'),
    path('channels/<uuid:pk>/stock/', views.channel_stock_allocations, name='channel_stock'),
    path('integrations/', views.integration_list, name='integration_list'),
    path('integrations/logs/', views.integration_logs, name='integration_logs'),
    path('integrations/marketplace/<uuid:pk>/', views.marketplace_detail, name='marketplace_detail'),
    path('integrations/payment-providers/', views.payment_providers_list, name='payment_providers'),
    path('integrations/shipping/', views.shipping_methods_list, name='shipping_methods'),
    path('sync/', views.sync_jobs_list, name='sync_jobs'),
]
