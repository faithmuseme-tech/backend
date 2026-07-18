from rest_framework import serializers
from .models import Product, ProductImage
from brands.serializers import BrandSerializer
from categories.serializers import CategorySerializer


def _proxy_url(url, request):
    """Rewrite a Cloudinary URL to go through our /media/ proxy."""
    if not url:
        return None
    import re
    # Match: https://res.cloudinary.com/<cloud>/image/upload/<version>/media/<path>
    m = re.search(r'res\.cloudinary\.com/[^/]+/image/upload/(?:v\d+/)?media/(.+)', url)
    if m:
        path = m.group(1)
        if request:
            return request.build_absolute_uri(f'/media/{path}')
        from django.conf import settings
        backend = getattr(settings, 'BACKEND_URL', 'https://web-production-1643f.up.railway.app')
        return f'{backend}/media/{path}'
    return url


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'is_primary', 'order')

    def get_image(self, obj):
        url = obj.image.url
        request = self.context.get('request')
        if not url.startswith('http'):
            url = request.build_absolute_uri(url) if request else f"http://127.0.0.1:8000{url}"
        return _proxy_url(url, request)


class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    delivery_charge = serializers.SerializerMethodField()
    brand_id = serializers.PrimaryKeyRelatedField(
        source='brand',
        queryset=__import__('brands.models', fromlist=['Brand']).Brand.objects.all(),
        write_only=True, required=False, allow_null=True
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source='category',
        queryset=__import__('categories.models', fromlist=['Category']).Category.objects.all(),
        write_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    discount = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    avg_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    commission_amount = serializers.ReadOnlyField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'brand', 'brand_id', 'category', 'category_id',
            'description', 'trader_price', 'price', 'original_price', 'delivery_charge',
            'commission_amount', 'stock', 'sku',
            'is_active', 'is_featured', 'is_new_arrival', 'is_best_seller', 'badge', 'specs',
            'images', 'discount', 'in_stock', 'avg_rating', 'review_count',
            'created_at',
        )
        read_only_fields = ('slug',)

    def get_delivery_charge(self, obj):
        return obj.effective_delivery_charge

    def validate_specs(self, value):
        import json
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return {}
        return value if isinstance(value, dict) else {}


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    delivery_charge = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'brand_name', 'category_name',
            'trader_price', 'price', 'original_price', 'delivery_charge', 'discount', 'in_stock',
            'stock', 'avg_rating', 'review_count', 'badge', 'primary_image',
            'is_featured', 'is_new_arrival', 'is_best_seller',
        )

    def get_avg_rating(self, obj):
        # Use annotated value if present (avoids extra DB query), else fall back to property
        val = getattr(obj, '_avg_rating', None)
        if val is None:
            val = obj.avg_rating
        return round(val, 1) if val else 0

    def get_review_count(self, obj):
        val = getattr(obj, '_review_count', None)
        return val if val is not None else obj.review_count

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not img:
            return None
        url = img.image.url
        request = self.context.get('request')
        if not url.startswith('http'):
            url = request.build_absolute_uri(url) if request else f"http://127.0.0.1:8000{url}"
        return _proxy_url(url, request)

    def get_delivery_charge(self, obj):
        return obj.effective_delivery_charge