from django.urls import path
from . import views

app_name = 'pricing'

urlpatterns = [
    path('', views.pricing_dashboard, name='pricing_dashboard'),
    path('price-lists/', views.price_list_list, name='price_list_list'),
    path('price-lists/create/', views.price_list_create, name='price_list_create'),
    path('price-lists/<int:pk>/', views.price_list_detail, name='price_list_detail'),
    path('price-lists/<int:pk>/edit/', views.price_list_edit, name='price_list_edit'),
    path('price-lists/<int:pk>/delete/', views.price_list_delete, name='price_list_delete'),
    path('price-lists/<int:pk>/entry/add/', views.entry_add, name='entry_add'),
    path('entry/<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('entry/<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('promotions/', views.promotion_list, name='promotion_list'),
    path('promotions/create/', views.promotion_create, name='promotion_create'),
    path('promotions/<int:pk>/edit/', views.promotion_edit, name='promotion_edit'),
    path('promotions/<int:pk>/delete/', views.promotion_delete, name='promotion_delete'),
    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/create/', views.coupon_create, name='coupon_create'),
    path('coupons/<int:pk>/edit/', views.coupon_edit, name='coupon_edit'),
    path('coupons/<int:pk>/delete/', views.coupon_delete, name='coupon_delete'),
    path('customer-prices/', views.customer_price_list, name='customer_price_list'),
    path('customer-prices/create/', views.customer_price_create, name='customer_price_create'),
    path('customer-prices/<int:pk>/edit/', views.customer_price_edit, name='customer_price_edit'),
    path('customer-prices/<int:pk>/delete/', views.customer_price_delete, name='customer_price_delete'),
    path('history/', views.price_history, name='price_history'),
    path('simulator/', views.pricing_simulator, name='pricing_simulator'),
    path('api/resolve/', views.api_resolve_price, name='api_resolve_price'),
]
