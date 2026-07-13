from rest_framework import serializers
from .models import Notification
from products.serializers import ProductListSerializer


class NotificationSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ('id', 'type', 'title', 'message', 'product', 'product_slug',
                  'product_image', 'order_id', 'is_read', 'created_at')

    def get_product_image(self, obj):
        if not obj.product:
            return None
        img = obj.product.images.filter(is_primary=True).first() or obj.product.images.first()
        if not img:
            return None
        url = img.image.url
        request = self.context.get('request')
        if url.startswith('http'):
            return url
        return request.build_absolute_uri(url) if request else url
