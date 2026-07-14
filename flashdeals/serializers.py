from rest_framework import serializers
from .models import FlashDeal
from products.serializers import ProductListSerializer


class FlashDealSerializer(serializers.ModelSerializer):
    product_detail  = ProductListSerializer(source='product', read_only=True)
    discount_percent = serializers.ReadOnlyField()
    sold_percent    = serializers.ReadOnlyField()
    remaining       = serializers.ReadOnlyField()
    is_live         = serializers.ReadOnlyField()

    class Meta:
        model = FlashDeal
        fields = (
            'id', 'product', 'product_detail', 'deal_price',
            'stock_count', 'sold_count', 'remaining', 'sold_percent',
            'discount_percent', 'is_live',
            'starts_at', 'ends_at', 'is_active', 'created_at',
        )
        read_only_fields = ('id', 'sold_count', 'created_at')

    def validate(self, data):
        product = data.get('product')
        deal_price = data.get('deal_price')
        if product and deal_price and deal_price >= product.price:
            raise serializers.ValidationError(
                {'deal_price': 'Deal price must be lower than the product price.'}
            )
        return data
