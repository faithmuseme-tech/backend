from django.test import TestCase

from orders.serializers import calculate_delivery_fee


class DeliveryFeeTests(TestCase):
    def test_delivery_fee_matches_location_rules(self):
        self.assertEqual(calculate_delivery_fee('Kampala'), 5000)
        self.assertEqual(calculate_delivery_fee('Mubende'), 10000)
        self.assertEqual(calculate_delivery_fee('Fort Portal'), 10000)
        self.assertEqual(calculate_delivery_fee('Mbarara'), 10000)
        self.assertEqual(calculate_delivery_fee('Gulu'), 10000)
        self.assertEqual(calculate_delivery_fee('Northern Uganda'), 10000)
        self.assertEqual(calculate_delivery_fee('Jinja'), 12000)
