from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from products.models import Product


def one_week_from_now():
    return timezone.now() + timedelta(weeks=1)


class FlashDeal(models.Model):
    product     = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='flash_deals')
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flash_deals')
    deal_price  = models.DecimalField(max_digits=10, decimal_places=2)
    stock_count = models.PositiveIntegerField(default=50)
    sold_count  = models.PositiveIntegerField(default=0)
    starts_at   = models.DateTimeField(default=timezone.now)
    ends_at     = models.DateTimeField(default=one_week_from_now)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Flash Deal: {self.product.name}"

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at and self.sold_count < self.stock_count

    @property
    def discount_percent(self):
        original = self.product.original_price or self.product.price
        if original and original > self.deal_price:
            return round((1 - self.deal_price / original) * 100)
        return 0

    @property
    def sold_percent(self):
        if not self.stock_count:
            return 0
        return round((self.sold_count / self.stock_count) * 100)

    @property
    def remaining(self):
        return max(self.stock_count - self.sold_count, 0)
