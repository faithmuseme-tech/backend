from rest_framework import serializers
from .models import Brand


class BrandSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo', 'description', 'is_active', 'product_count')

    def get_product_count(self, obj):
        # Use annotated value from queryset — no extra DB query
        val = getattr(obj, 'product_count', None)
        return val if val is not None else obj.products.filter(is_active=True).count()

    def get_logo(self, obj):
        if not obj.logo:
            return None
        url = obj.logo.url
        if url.startswith('http'):
            return url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url
