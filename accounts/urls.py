from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, ProfileView, ChangePasswordView, LogoutView,
    TraderRegisterView, TraderProfileView, PhoneTokenObtainPairView,
    CookiePreferenceView, DeleteAccountView, CloseAccountView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', PhoneTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('trader/register/', TraderRegisterView.as_view(), name='trader_register'),
    path('trader/profile/', TraderProfileView.as_view(), name='trader_profile'),
    path('cookie-preferences/', CookiePreferenceView.as_view(), name='cookie_preferences'),
    path('delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    path('close-account/', CloseAccountView.as_view(), name='close_account'),
]
