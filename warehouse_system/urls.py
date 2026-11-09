from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from core.views import set_language

urlpatterns = [
    path('admin/', admin.site.urls),
    path('set-language/', set_language, name='set_language'),
    path('', include('inventory.urls')),
    path('products/', include('products.urls')),
    path('warehouses/', include('warehouses.urls')),
    path('purchases/', include('purchases.urls')),
    path('sales/', include('sales.urls')),
    path('orders/', include('orders.urls')),
    path('lists/', include('spiskalar.urls')),
    path('contacts/', include('contacts.urls')),
    path('crm/', include('crm.urls')),
    path('pricing/', include('pricing.urls')),
    path('finance/', include('finance.urls')),
    path('reports/', include('reports.urls')),
    path('activity/', include('activity.urls')),
    path('notifications/', include('notifications.urls')),
    path('scanner/', include('scanner.urls')),
    path('pos/', include('pos.urls')),
    path('markings/', include('markings.urls')),
    path('documents/', include('documents.urls')),
    path('logistics/', include('logistics.urls')),
    path('import-export/', include('import_export.urls')),
    path('users/', include('users.urls')),
    path('ecommerce/', include('ecommerce.urls')),
    path('store/', include('storefront.urls')),
    path('integrations/', include('integrations.urls')),
    path('automation/', include('automation.urls')),
    path('ai/', include('sklat_ai.urls')),
    path('platform/', include('saas_platform.urls')),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('', views.welcome, name='welcome'),
    path('welcome/', views.welcome, name='welcome_page'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
