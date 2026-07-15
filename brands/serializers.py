from rest_framework import serializers
from .models import Brand


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
        if url.startswith('http'):
            return url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

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
