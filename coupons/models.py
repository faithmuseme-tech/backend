import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class PromotionConfig(models.Model):
    """
    Single-row table holding all configurable promotion thresholds/amounts.
    Change values here without touching code.
    """
    # Large-order coupon
    large_order_subtotal_threshold = models.PositiveIntegerField(default=200_000)
    large_order_delivery_threshold = models.PositiveIntegerField(default=100_000)
    large_order_coupon_amount      = models.PositiveIntegerField(default=15_000)

    # First-order discount
    first_order_min_total   = models.PositiveIntegerField(default=30_000)
    first_order_discount    = models.PositiveIntegerField(default=5_000)

    # Loyalty points
    points_per_delivery_unit  = models.PositiveIntegerField(default=10)   # points per UGX 10,000 delivery
    delivery_unit_size        = models.PositiveIntegerField(default=10_000)
    points_redemption_value   = models.PositiveIntegerField(default=100)  # UGX per point
    points_redemption_minimum = models.PositiveIntegerField(default=150)  # min points to redeem

    class Meta:
        verbose_name = 'Promotion Config'

    def __str__(self):
        return 'Promotion Configuration'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def _generate_coupon_code():
    return uuid.uuid4().hex[:10].upper()


class Coupon(models.Model):
    TYPE_LARGE_ORDER  = 'large_order'
    TYPE_FIRST_ORDER  = 'first_order'
    TYPE_MANUAL       = 'manual'
    TYPE_CHOICES = [
        (TYPE_LARGE_ORDER, 'Large Order Reward'),
        (TYPE_FIRST_ORDER, 'First Order Discount'),
        (TYPE_MANUAL,      'Manual / Admin'),
    ]

    code         = models.CharField(max_length=20, unique=True, default=_generate_coupon_code)
    coupon_type  = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_MANUAL)
    discount     = models.PositiveIntegerField(help_text='Discount amount in UGX')
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='coupons', null=True, blank=True,
        help_text='If set, only this user can use the coupon'
    )
    is_active    = models.BooleanField(default=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    usage_limit  = models.PositiveIntegerField(default=1)
    times_used   = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.code} — UGX {self.discount:,}'

    def is_valid_for(self, user):
        if not self.is_active:
            return False, 'Coupon is inactive.'
        if self.expires_at and timezone.now() > self.expires_at:
            return False, 'Coupon has expired.'
        if self.times_used >= self.usage_limit:
            return False, 'Coupon usage limit reached.'
        if self.user and self.user != user:
            return False, 'Coupon is not valid for your account.'
        if CouponUsage.objects.filter(coupon=self, user=user).exists():
            return False, 'You have already used this coupon.'
        return True, None


class CouponUsage(models.Model):
    coupon     = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_usages')
    order_id   = models.IntegerField()
    used_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('coupon', 'user')

    def __str__(self):
        return f'{self.user.email} used {self.coupon.code}'


class LoyaltyAccount(models.Model):
    user           = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty')
    points_balance = models.IntegerField(default=0)
    points_earned  = models.IntegerField(default=0)
    points_redeemed = models.IntegerField(default=0)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} — {self.points_balance} pts'

    @classmethod
    def for_user(cls, user):
        account, _ = cls.objects.get_or_create(user=user)
        return account


class LoyaltyTransaction(models.Model):
    TYPE_EARN   = 'earn'
    TYPE_REDEEM = 'redeem'
    TYPE_REVERSE = 'reverse'
    TYPE_CHOICES = [
        (TYPE_EARN,    'Earned'),
        (TYPE_REDEEM,  'Redeemed'),
        (TYPE_REVERSE, 'Reversed'),
    ]

    account    = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    order_id   = models.IntegerField()
    tx_type    = models.CharField(max_length=10, choices=TYPE_CHOICES)
    points     = models.IntegerField()  # positive = earn, negative = redeem/reverse
    note       = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.account.user.email} {self.tx_type} {self.points} pts (order {self.order_id})'
