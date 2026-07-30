from django.urls import path
from .views import (
    OrderListView, OrderDetailView, CreateOrderView, TraderOrderListView, TraderStatsView,
    ReturnRequestCreateView, AdminReturnRequestListView, AdminReturnRequestDetailView,
)

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('create/', CreateOrderView.as_view(), name='create_order'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('trader/', TraderOrderListView.as_view(), name='trader_orders'),
    path('trader/stats/', TraderStatsView.as_view(), name='trader_stats'),
    path('returns/', ReturnRequestCreateView.as_view(), name='return_requests'),
    path('admin/returns/', AdminReturnRequestListView.as_view(), name='admin_return_list'),
    path('admin/returns/<int:pk>/', AdminReturnRequestDetailView.as_view(), name='admin_return_detail'),
]
