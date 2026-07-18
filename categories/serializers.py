from rest_framework import serializers
from .models import Category
import re as _re


def _proxy_url(url, request):
    if not url:
        return None
    m = _re.search(r'res\.cloudinary\.com/[^/]+/image/upload/(?:v\d+/)?media/(.+)', url)
    if m:
        path = m.group(1)
        if request:
            return request.build_absolute_uri(f'/media/{path}')
        from django.conf import settings
        backend = getattr(settings, 'BACKEND_URL', 'https://web-production-1643f.up.railway.app')
        return f'{backend}/media/{path}'
    return url


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.ReadOnlyField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image', 'icon', 'description', 'parent', 'product_count', 'is_active')
        read_only_fields = ('slug',)

    def get_image(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get('request')
        if not url.startswith('http'):
            url = request.build_absolute_uri(url) if request else url
        return _proxy_url(url, request)

    def validate_is_active(self, value):
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return value
