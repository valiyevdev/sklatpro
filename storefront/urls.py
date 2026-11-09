from django.urls import path
from . import views

app_name = 'storefront'

urlpatterns = [
    path('', views.storefront_home, name='home'),
    path('catalog/', views.product_catalog, name='catalog'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('category/<slug:slug>/', views.category_view, name='category'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/item/<uuid:item_id>/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/coupon/', views.apply_coupon, name='apply_coupon'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('order/confirmation/', views.order_confirmation, name='order_confirmation'),
    path('order/tracking/', views.order_tracking, name='order_tracking'),
    path('account/', views.customer_account, name='account'),
    path('wishlist/toggle/', views.wishlist_toggle, name='wishlist_toggle'),
    path('review/add/', views.add_review, name='add_review'),
    path('api/cart-count/', views.api_cart_count, name='api_cart_count'),
]
