from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ('id', 'product', 'product_name', 'product_slug', 'product_image',
                  'user_name', 'user_email', 'user_avatar', 'rating', 'title', 'body', 'created_at')
        read_only_fields = ('id', 'product', 'user_name', 'user_email', 'user_avatar',
                            'product_name', 'product_slug', 'product_image', 'created_at')

    def get_user_name(self, obj):
        full = obj.user.get_full_name().strip()
        return full if full else obj.user.username

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        if obj.user.avatar:
            url = obj.user.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_product_image(self, obj):
        if not obj.product:
            return None
        img = obj.product.images.filter(is_primary=True).first() or obj.product.images.first()
        if not img:
            return None
        url = img.image.url
        if url.startswith('http'):
            return url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url
