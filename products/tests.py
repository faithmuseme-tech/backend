from decimal import Decimal
from django.test import TestCase
from .models import Product
from .serializers import ProductSerializer


class ProductDeliveryChargeTests(TestCase):
    def test_serializer_uses_default_delivery_charge_for_zero_values(self):
        product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=Decimal('10000.00'),
            original_price=Decimal('15000.00'),
            delivery_charge=Decimal('0.00'),
        )

        serializer = ProductSerializer(product)

        self.assertEqual(Decimal(str(serializer.data['delivery_charge'])), Decimal('5000.00'))
