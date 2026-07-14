from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image', 'icon', 'description', 'parent', 'product_count', 'is_active')
        read_only_fields = ('slug',)

    def validate_is_active(self, value):
        # multipart/form-data sends booleans as strings
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return value
