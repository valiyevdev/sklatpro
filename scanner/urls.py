from django.urls import path
from . import views

app_name = 'scanner'

urlpatterns = [
    path('', views.scanner_view, name='scanner_view'),
    path('search/', views.scanner_search, name='scanner_search'),
]
