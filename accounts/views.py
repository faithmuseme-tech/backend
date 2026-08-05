from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from .serializers import (
    RegisterSerializer, UserSerializer, ChangePasswordSerializer,
    TraderRegisterSerializer, TraderProfileSerializer,
    PhoneTokenObtainPairSerializer, CookiePreferenceSerializer,
)
from .models import TraderProfile, CookiePreference
from .email import send_welcome_email

User = get_user_model()


class PhoneTokenObtainPairView(TokenObtainPairView):
    serializer_class = PhoneTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_welcome_email(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'Incorrect current password.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password updated successfully.'})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data['refresh']).blacklist()
        except Exception:
            pass
        return Response({'message': 'Logged out.'})


class TraderRegisterView(generics.CreateAPIView):
    serializer_class = TraderRegisterSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if hasattr(request.user, 'trader_profile'):
            return Response({'error': 'Trader profile already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(TraderProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class TraderProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TraderProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.trader_profile


class CookiePreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pref, _ = CookiePreference.objects.get_or_create(user=request.user)
        return Response(CookiePreferenceSerializer(pref).data)

    def post(self, request):
        pref, _ = CookiePreference.objects.get_or_create(user=request.user)
        serializer = CookiePreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DeleteAccountView(APIView):
    """Permanently deletes the user account and all associated data."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        try:
            RefreshToken(request.data.get('refresh', '')).blacklist()
        except Exception:
            pass
        user.delete()
        return Response({'message': 'Account permanently deleted.'}, status=status.HTTP_204_NO_CONTENT)


class CloseAccountView(APIView):
    """Deactivates the account (soft close — keeps data, blocks login)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        try:
            RefreshToken(request.data.get('refresh', '')).blacklist()
        except Exception:
            pass
        return Response({'message': 'Account closed.'}, status=status.HTTP_200_OK)
