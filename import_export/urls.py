from django.urls import path
from . import views

app_name = 'import_export'

urlpatterns = [
    path('', views.import_export_index, name='import_export_index'),
    path('import/products/', views.import_products, name='import_products'),
    path('export/products/', views.export_products, name='export_products'),
]
