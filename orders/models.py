import uuid
import random
import string

from django.db import models
from django.conf import settings
from products.models import Product


def _generate_secret_word():
    """e.g. BLUE-7429"""
    colors = ["BLUE", "RED", "GOLD", "LIME", "TEAL", "PINK", "JADE", "RUBY", "SAGE", "BOLT"]
    digits = "".join(random.choices(string.digits, k=4))
    return f"{random.choice(colors)}-{digits}"


class Order(models.Model):
    order_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user_crud_number = models.UUIDField(editable=False, db_index=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('pickup', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_country = models.CharField(max_length=100)
    shipping_zip = models.CharField(max_length=20)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code_used = models.CharField(max_length=20, blank=True)
    points_used = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    secret_word = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.user and not self.user_crud_number:
            self.user_crud_number = self.user.crud_number
        if not self.secret_word:
            self.secret_word = _generate_secret_word()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number} — {self.user.email}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=255)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    selected_options = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"

    @property
    def subtotal(self):
        return self.product_price * self.quantity


class ReturnRequest(models.Model):
    REASON_CHOICES = [
        ('defective', 'Defective / Faulty Product'),
        ('wrong_item', 'Wrong Item Delivered'),
        ('not_as_described', 'Not as Described'),
        ('damaged_delivery', 'Damaged During Delivery'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    order       = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests')
    items       = models.ManyToManyField(OrderItem, blank=True)
    reason      = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return #{self.id} — Order {str(self.order.order_number)[:8].upper()}"
