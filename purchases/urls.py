from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='purchase_list'),
    path('dashboard/', views.purchase_dashboard, name='purchase_dashboard'),
    path('create/', views.purchase_create, name='purchase_create'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('<int:pk>/edit/', views.purchase_update, name='purchase_update'),
    path('<int:pk>/delete/', views.purchase_delete, name='purchase_delete'),
    path('<int:pk>/receive/', views.purchase_receive, name='purchase_receive'),
    path('<int:pk>/update-status/', views.purchase_update_status, name='purchase_update_status'),
    path('<int:pk>/return/', views.purchase_return_create, name='purchase_return_create'),
    path('returns/<int:pk>/', views.purchase_return_detail, name='purchase_return_detail'),
    path('returns/<int:pk>/update-status/', views.purchase_return_update_status, name='purchase_return_update_status'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_update, name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
]
