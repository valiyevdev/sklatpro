from django.urls import path
from . import views

app_name = 'markings'

urlpatterns = [
    path('', views.marking_dashboard, name='marking_dashboard'),
    path('gtin/', views.gtin_list, name='gtin_list'),
    path('gtin/create/', views.gtin_create, name='gtin_create'),
    path('gtin/<int:pk>/', views.gtin_detail, name='gtin_detail'),
    path('codes/', views.marking_list, name='marking_list'),
    path('codes/create/', views.marking_create, name='marking_create'),
    path('codes/<int:pk>/', views.marking_detail, name='marking_detail'),
    path('codes/<int:pk>/verify/', views.marking_verify, name='marking_verify'),
    path('codes/<int:pk>/history/', views.marking_history, name='marking_history'),
    path('aggregation/', views.aggregation_list, name='aggregation_list'),
    path('aggregation/create/', views.aggregation_create, name='aggregation_create'),
    path('aggregation/<int:pk>/', views.aggregation_detail, name='aggregation_detail'),
    path('aggregation/<int:pk>/disaggregate/', views.aggregation_disaggregate, name='aggregation_disaggregate'),
    path('validate/', views.code_validate, name='code_validate'),
    path('api/validate/', views.code_validate_api, name='code_validate_api'),
    path('trace/', views.trace_product, name='trace_product'),
    path('trace/<int:product_id>/', views.traceability_timeline, name='traceability_timeline'),
]
