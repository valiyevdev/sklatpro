from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    path('', views.crm_dashboard, name='crm_dashboard'),
    path('customers/', views.customer_crm_list, name='customer_crm_list'),
    path('customers/export/', views.customer_export, name='customer_export'),
    path('<int:pk>/', views.customer_360, name='customer_360'),
    path('<int:pk>/action/', views.customer_quick_action, name='customer_quick_action'),
    path('<int:customer_id>/document/upload/', views.document_upload, name='document_upload'),
    path('document/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('<int:customer_id>/communication/', views.communication_create, name='communication_create'),
    path('<int:customer_id>/note/', views.note_create, name='note_create'),
    path('note/<int:pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:customer_id>/task/', views.task_create, name='task_create'),
    path('task/<int:pk>/status/', views.task_update_status, name='task_update_status'),
    path('segments/', views.segment_list, name='segment_list'),
    path('segments/create/', views.segment_create, name='segment_create'),
    path('segments/<int:pk>/delete/', views.segment_delete, name='segment_delete'),
    path('<int:customer_id>/segment/assign/', views.segment_assign, name='segment_assign'),
    path('<int:customer_id>/segment/<int:assignment_id>/remove/', views.segment_remove, name='segment_remove'),
    path('tags/', views.tag_list, name='tag_list'),
    path('tags/create/', views.tag_create, name='tag_create'),
    path('tags/<int:pk>/delete/', views.tag_delete, name='tag_delete'),
    path('<int:customer_id>/tag/assign/', views.tag_assign, name='tag_assign'),
    path('<int:customer_id>/tag/<int:assignment_id>/remove/', views.tag_remove, name='tag_remove'),
    path('rfm/', views.rfm_analyze, name='rfm_analyze'),
]
