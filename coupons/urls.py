from django.urls import path
from .views import CheckoutPreviewView, ValidateCouponView, LoyaltyView, MyCouponsView

urlpatterns = [
    path('preview/', CheckoutPreviewView.as_view(), name='checkout_preview'),
    path('validate-coupon/', ValidateCouponView.as_view(), name='validate_coupon'),
    path('loyalty/', LoyaltyView.as_view(), name='loyalty'),
    path('my-coupons/', MyCouponsView.as_view(), name='my_coupons'),
]
