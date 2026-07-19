from django.urls import path
from .views import (
    AdminStatsView, AdminUserListView, AdminUserDetailView,
    AdminTraderListView, AdminTraderApproveView,
    AdminOrderListView, AdminOrderDetailView, AdminOrderStatusUpdateView, AdminOrderLookupView,
    AdminProductListView, AdminProductDetailView, AdminProductImageView, AdminProductToggleView,
    AdminResetPasswordView, SiteSettingsView, NewsletterSubscribeView,
)

urlpatterns = [
    path('stats/', AdminStatsView.as_view(), name='admin_stats'),
    path('users/', AdminUserListView.as_view(), name='admin_users'),
    path('users/<int:pk>/', AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('users/<int:pk>/reset-password/', AdminResetPasswordView.as_view(), name='admin_reset_password'),
    path('traders/', AdminTraderListView.as_view(), name='admin_traders'),
    path('traders/<int:pk>/action/', AdminTraderApproveView.as_view(), name='admin_trader_action'),
    path('orders/', AdminOrderListView.as_view(), name='admin_orders'),
    path('orders/<int:pk>/', AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('orders/<int:pk>/status/', AdminOrderStatusUpdateView.as_view(), name='admin_order_status'),
    path('orders/lookup/', AdminOrderLookupView.as_view(), name='admin_order_lookup'),
    path('products/', AdminProductListView.as_view(), name='admin_products'),
    path('products/<int:pk>/', AdminProductDetailView.as_view(), name='admin_product_detail'),
    path('products/<int:pk>/images/', AdminProductImageView.as_view(), name='admin_product_images'),
    path('products/<int:pk>/toggle/', AdminProductToggleView.as_view(), name='admin_product_toggle'),
    path('settings/', SiteSettingsView.as_view(), name='admin_settings'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter_subscribe'),
]
