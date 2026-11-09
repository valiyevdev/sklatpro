from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('create/', views.product_create, name='product_create'),
    path('search-api/', views.product_search_api, name='product_search_api'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_update, name='product_update'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('<int:pk>/duplicate/', views.product_duplicate, name='product_duplicate'),
    path('<int:pk>/barcode/', views.product_barcode, name='product_barcode'),
    path('<int:pk>/qrcode/', views.product_qrcode, name='product_qrcode'),
    path('<int:product_pk>/variants/create/', views.variant_create, name='variant_create'),
    path('<int:product_pk>/variants/<int:pk>/edit/', views.variant_update, name='variant_update'),
    path('<int:product_pk>/variants/<int:pk>/delete/', views.variant_delete, name='variant_delete'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('brands/', views.brand_list, name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),
    path('brands/<int:pk>/edit/', views.brand_update, name='brand_update'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    path('units/', views.unit_list, name='unit_list'),
    path('units/create/', views.unit_create, name='unit_create'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
]
