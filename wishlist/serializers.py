from rest_framework import serializers
from .models import Wishlist
from products.serializers import ProductListSerializer


class WishlistSerializer(serializers.ModelSerializer):
    products = ProductListSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ('id', 'products', 'updated_at')
