from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.documents_dashboard, name='documents_dashboard'),
    path('list/', views.document_list, name='document_list'),
    path('create/', views.document_create, name='document_create'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/edit/', views.document_edit, name='document_edit'),
    path('<int:pk>/status/', views.document_status_change, name='document_status_change'),
    path('<int:pk>/approve/', views.document_approve, name='document_approve'),
    path('<int:pk>/cancel/', views.document_cancel, name='document_cancel'),
    path('<int:pk>/archive/', views.document_archive, name='document_archive'),
    path('<int:pk>/preview/', views.document_preview, name='document_preview'),
    path('<int:pk>/print/', views.document_print, name='document_print'),
    path('<int:pk>/version/', views.document_new_version, name='document_new_version'),
    path('<int:pk>/versions/', views.document_versions, name='document_versions'),
    path('<int:pk>/attachments/upload/', views.document_attachment_upload, name='document_attachment_upload'),
    path('attachment/<int:att_pk>/download/', views.document_download, name='document_download'),
    path('attachment/<int:att_pk>/delete/', views.document_attachment_delete, name='document_attachment_delete'),
    path('templates/', views.document_template_list, name='document_template_list'),
    path('templates/create/', views.document_template_create, name='document_template_create'),
    path('edo/', views.edo_dashboard, name='edo_dashboard'),
    path('edo/<int:pk>/send/', views.edo_send, name='edo_send'),
    path('edo/<int:pk>/status/', views.edo_status, name='edo_status'),
    path('<int:pk>/signature/request/', views.document_signature_request, name='document_signature_request'),
    path('<int:pk>/signature/sign/', views.document_sign, name='document_sign'),
]
