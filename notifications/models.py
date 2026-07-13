from django.db import models
from django.conf import settings
from products.models import Product


class Notification(models.Model):
    TYPE_RATE_PRODUCT = 'rate_product'
    TYPE_ORDER_UPDATE = 'order_update'
    TYPE_CHOICES = [
        (TYPE_RATE_PRODUCT, 'Rate Product'),
        (TYPE_ORDER_UPDATE, 'Order Update'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    order_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — {self.title}"
