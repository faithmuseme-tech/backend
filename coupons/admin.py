from django.contrib import admin
from .models import PromotionConfig, Coupon, CouponUsage, LoyaltyAccount, LoyaltyTransaction


@admin.register(PromotionConfig)
class PromotionConfigAdmin(admin.ModelAdmin):
    list_display = (
        'large_order_subtotal_threshold', 'large_order_delivery_threshold',
        'large_order_coupon_amount', 'first_order_min_total', 'first_order_discount',
        'points_per_delivery_unit', 'delivery_unit_size',
        'points_redemption_value', 'points_redemption_minimum',
    )

    def has_add_permission(self, request):
        return not PromotionConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'coupon_type', 'discount', 'user', 'is_active', 'times_used', 'usage_limit', 'expires_at', 'created_at')
    list_filter  = ('coupon_type', 'is_active')
    search_fields = ('code', 'user__email')
    readonly_fields = ('times_used', 'created_at')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order_id', 'used_at')
    readonly_fields = ('used_at',)


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'points_balance', 'points_earned', 'points_redeemed', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('updated_at',)


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'tx_type', 'points', 'order_id', 'note', 'created_at')
    list_filter  = ('tx_type',)
    readonly_fields = ('created_at',)
