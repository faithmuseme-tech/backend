from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import TraderProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    email     = serializers.EmailField(required=False, allow_blank=True, default="")
    phone     = serializers.CharField(required=True)

    class Meta:
        model  = User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name', 'phone', 'city', 'address')

    def validate_phone(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate_email(self, value):
        value = value.strip() if value else ""
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        email = validated_data.pop('email', '').strip()
        phone = validated_data['phone']
        # Use email as username if provided, otherwise derive from phone
        validated_data.setdefault('username', email if email else f"user_{phone}")
        validated_data['email'] = email if email else None
        return User.objects.create_user(**validated_data)


class TraderProfileSerializer(serializers.ModelSerializer):
    user_email      = serializers.EmailField(source='user.email', read_only=True)
    user_name       = serializers.SerializerMethodField()
    user_phone      = serializers.CharField(source='user.phone', read_only=True)
    user_is_active  = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = TraderProfile
        fields = (
            'id', 'business_name', 'business_email', 'business_phone',
            'business_address', 'business_city', 'business_country',
            'description', 'logo', 'status', 'is_approved', 'created_at',
            'user_email', 'user_name', 'user_phone', 'user_is_active',
        )
        read_only_fields = ('id', 'status', 'is_approved', 'created_at')

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username


class UserSerializer(serializers.ModelSerializer):
    trader_profile = TraderProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'crud_number', 'username', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'address', 'city', 'country', 'zip_code',
            'is_trader', 'is_admin', 'trader_profile',
        )
        read_only_fields = ('id', 'crud_number', 'is_trader', 'is_admin')


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
