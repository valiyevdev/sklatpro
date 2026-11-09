from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('dashboard/', views.sale_dashboard, name='sale_dashboard'),
    path('create/', views.sale_create, name='sale_create'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/edit/', views.sale_update, name='sale_update'),
    path('<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    path('<int:pk>/update-status/', views.sale_update_status, name='sale_update_status'),
    path('<int:pk>/reserve/', views.sale_reserve, name='sale_reserve'),
    path('<int:pk>/payment/', views.sale_payment_create, name='sale_payment_create'),
    path('<int:pk>/return/', views.sale_return_create, name='sale_return_create'),
    path('returns/<int:pk>/', views.sale_return_detail, name='sale_return_detail'),
    path('returns/<int:pk>/update-status/', views.sale_return_update_status, name='sale_return_update_status'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
]
