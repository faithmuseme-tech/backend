from django.urls import path
from .views import FlashDealListView, TraderFlashDealListCreateView, TraderFlashDealDeleteView

urlpatterns = [
    path('', FlashDealListView.as_view(), name='flash_deal_list'),
    path('trader/', TraderFlashDealListCreateView.as_view(), name='trader_flash_deals'),
    path('trader/<int:pk>/', TraderFlashDealDeleteView.as_view(), name='trader_flash_deal_delete'),
]
