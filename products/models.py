import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage
from brands.models import Brand
from categories.models import Category


class UserBehavior(models.Model):
    """Tracks anonymous/authenticated product view events for recommendations."""
    session_key = models.CharField(max_length=64, db_index=True)  # anonymous or user id
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='behavior_events')
    seconds_spent = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Product(models.Model):
    DEFAULT_DELIVERY_CHARGE = Decimal('5000.00')

    COMMISSION_RATE = Decimal('0.10')

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    description = models.TextField(blank=True)
    trader_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Price set by trader (before 10% platform commission)')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Final price shown to customers (trader_price + 10%)')
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Delivery charge in UGX')
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    badge = models.CharField(max_length=50, blank=True)
    specs = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def discount(self):
        if self.price and self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100)
        return 0

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def avg_rating(self):
        from django.db.models import Avg
        result = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(result, 1) if result else 0

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def effective_delivery_charge(self):
        if self.delivery_charge and self.delivery_charge > 0:
            return self.delivery_charge
        return self.DEFAULT_DELIVERY_CHARGE

    @property
    def commission_amount(self):
        if self.trader_price:
            return (self.trader_price * self.COMMISSION_RATE).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = 'SKU-' + str(uuid.uuid4())[:8].upper()
        if self.delivery_charge is None or self.delivery_charge <= 0:
            self.delivery_charge = self.DEFAULT_DELIVERY_CHARGE
        # Auto-calculate price from trader_price + 10% commission
        if self.trader_price:
            self.price = (self.trader_price * (1 + self.COMMISSION_RATE)).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/', storage=MediaCloudinaryStorage())
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} - image {self.order}"

