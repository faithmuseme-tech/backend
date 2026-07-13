from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'product', 'product_name', 'user_name', 'user_email', 'user_avatar', 'rating', 'title', 'body', 'created_at')
        read_only_fields = ('id', 'user_name', 'user_email', 'user_avatar', 'product_name', 'created_at')

    def get_user_name(self, obj):
        full = obj.user.get_full_name().strip()
        return full if full else obj.user.username

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        if obj.user.avatar:
            url = obj.user.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None
