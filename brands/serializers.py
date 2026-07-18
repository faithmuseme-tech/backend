from rest_framework import serializers
from .models import Brand
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


class BrandSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    logo_upload = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo', 'logo_upload', 'description', 'is_active', 'product_count')
        read_only_fields = ('slug',)

    def get_product_count(self, obj):
        val = getattr(obj, 'product_count', None)
        return val if val is not None else obj.products.filter(is_active=True).count()

    def get_logo(self, obj):
        if not obj.logo:
            return None
        url = obj.logo.url
        request = self.context.get('request')
        if not url.startswith('http'):
            url = request.build_absolute_uri(url) if request else url
        return _proxy_url(url, request)

    def create(self, validated_data):
        logo = validated_data.pop('logo_upload', None)
        instance = super().create(validated_data)
        if logo:
            instance.logo = logo
            instance.save()
        return instance

    def update(self, instance, validated_data):
        logo = validated_data.pop('logo_upload', None)
        instance = super().update(instance, validated_data)
        if logo:
            instance.logo = logo
            instance.save()
        return instance
