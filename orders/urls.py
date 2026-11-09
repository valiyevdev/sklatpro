from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('dashboard/', views.order_dashboard, name='order_dashboard'),
    path('create/', views.order_create, name='order_create'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/edit/', views.order_update, name='order_update'),
    path('<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('<int:pk>/update-status/', views.order_update_status, name='order_update_status'),
    path('<int:pk>/reserve/', views.order_reserve, name='order_reserve'),
    path('<int:pk>/payment/', views.order_payment_create, name='order_payment_create'),
    path('<int:pk>/duplicate/', views.order_duplicate, name='order_duplicate'),
    path('<int:pk>/fulfillment/', views.order_update_fulfillment, name='order_update_fulfillment'),
]
