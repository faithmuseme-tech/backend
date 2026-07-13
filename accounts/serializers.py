from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import TraderProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name', 'phone')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        return User.objects.create_user(**validated_data)


class TraderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraderProfile
        fields = (
            'id', 'business_name', 'business_email', 'business_phone',
            'business_address', 'business_city', 'business_country',
            'description', 'logo', 'status', 'is_approved', 'created_at',
        )
        read_only_fields = ('id', 'status', 'is_approved', 'created_at')


class UserSerializer(serializers.ModelSerializer):
    trader_profile = TraderProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'crud_number', 'username', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'address', 'city', 'country', 'zip_code',
            'is_trader', 'is_admin', 'trader_profile',
        )
        read_only_fields = ('id', 'crud_number', 'email', 'is_trader', 'is_admin')


class AdminUserSerializer(serializers.ModelSerializer):
    trader_profile = TraderProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'crud_number', 'username', 'email', 'first_name', 'last_name', 'phone',
            'is_active', 'is_trader', 'is_admin', 'is_staff',
            'trader_profile', 'date_joined',
        )
        read_only_fields = ('id', 'crud_number', 'email', 'date_joined')


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class TraderRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraderProfile
        fields = (
            'business_name', 'business_email', 'business_phone',
            'business_address', 'business_city', 'business_country', 'description',
        )

    def create(self, validated_data):
        user = self.context['request'].user
        user.is_trader = True
        user.save()
        return TraderProfile.objects.create(user=user, **validated_data)
