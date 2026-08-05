from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from orders.serializers import calculate_delivery_fee
from orders.models import Order
from cart.models import Cart
from .models import Coupon, CouponUsage, LoyaltyAccount, LoyaltyTransaction, PromotionConfig


class CheckoutPreviewView(APIView):
    """
    Returns all promotion config values, eligible coupons, and a full price
    breakdown for the current cart + shipping city.
    Frontend uses this — never hardcodes any threshold or discount value.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        city = request.data.get('shipping_city', '')
        coupon_code = (request.data.get('coupon_code') or '').strip().upper()
        redeem_points = bool(request.data.get('redeem_points', False))

        cfg = PromotionConfig.get()

        # Cart
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = list(cart.items.select_related('product').all())
        except Cart.DoesNotExist:
            cart_items = []

        subtotal     = int(sum(item.subtotal for item in cart_items))
        delivery_fee = calculate_delivery_fee(city, cart_items)

        # ── Large-order coupon ──────────────────────────────────────────────
        large_order_eligible = (
            subtotal >= cfg.large_order_subtotal_threshold and
            delivery_fee >= cfg.large_order_delivery_threshold
        )
        large_order_coupon = None
        if large_order_eligible:
            existing = Coupon.objects.filter(
                user=request.user,
                coupon_type=Coupon.TYPE_LARGE_ORDER,
                is_active=True,
            ).exclude(usages__user=request.user).first()
            if not existing:
                existing = Coupon.objects.create(
                    coupon_type=Coupon.TYPE_LARGE_ORDER,
                    discount=cfg.large_order_coupon_amount,
                    user=request.user,
                    usage_limit=1,
                )
            large_order_coupon = {'code': existing.code, 'discount': existing.discount}

        # ── First-order discount ────────────────────────────────────────────
        first_order_eligible = False
        first_order_coupon   = None
        has_previous = Order.objects.filter(
            user=request.user,
            status__in=['confirmed', 'shipped', 'pickup', 'delivered']
        ).exists()
        if not has_previous and (subtotal + delivery_fee) >= cfg.first_order_min_total:
            first_order_eligible = True
            existing_fo = Coupon.objects.filter(
                user=request.user,
                coupon_type=Coupon.TYPE_FIRST_ORDER,
                is_active=True,
            ).exclude(usages__user=request.user).first()
            if not existing_fo:
                existing_fo = Coupon.objects.create(
                    coupon_type=Coupon.TYPE_FIRST_ORDER,
                    discount=cfg.first_order_discount,
                    user=request.user,
                    usage_limit=1,
                )
            first_order_coupon = {'code': existing_fo.code, 'discount': existing_fo.discount}

        # ── Validate entered coupon ─────────────────────────────────────────
        coupon_discount = 0
        coupon_error    = None
        applied_coupon  = None
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                valid, reason = coupon.is_valid_for(request.user)
                if valid:
                    coupon_discount = coupon.discount
                    applied_coupon  = {'code': coupon.code, 'discount': coupon.discount}
                else:
                    coupon_error = reason
            except Coupon.DoesNotExist:
                coupon_error = 'Invalid coupon code.'

        # ── Loyalty points ──────────────────────────────────────────────────
        account        = LoyaltyAccount.for_user(request.user)
        points_balance = account.points_balance
        points_discount = 0
        points_error    = None
        points_used     = 0
        if redeem_points:
            if points_balance < cfg.points_redemption_minimum:
                points_error = (
                    f'You need at least {cfg.points_redemption_minimum} points to redeem. '
                    f'You have {points_balance}.'
                )
            else:
                points_used     = points_balance
                points_discount = points_used * cfg.points_redemption_value

        # Cap: coupon can reduce subtotal+delivery, points only reduce subtotal
        coupon_discount = min(coupon_discount, subtotal + delivery_fee)
        points_discount = min(points_discount, subtotal)
        grand_total     = max(0, subtotal + delivery_fee - coupon_discount - points_discount)

        return Response({
            'subtotal':        subtotal,
            'delivery_fee':    delivery_fee,
            'coupon_discount': coupon_discount,
            'points_discount': points_discount,
            'grand_total':     grand_total,
            'applied_coupon':  applied_coupon,
            'coupon_error':    coupon_error,
            'points_error':    points_error,
            'points_used':     points_used,

            'large_order_eligible': large_order_eligible,
            'large_order_coupon':   large_order_coupon,
            'first_order_eligible': first_order_eligible,
            'first_order_coupon':   first_order_coupon,

            'config': {
                'large_order_subtotal_threshold': cfg.large_order_subtotal_threshold,
                'large_order_delivery_threshold': cfg.large_order_delivery_threshold,
                'large_order_coupon_amount':      cfg.large_order_coupon_amount,
                'first_order_min_total':          cfg.first_order_min_total,
                'first_order_discount':           cfg.first_order_discount,
                'points_redemption_value':        cfg.points_redemption_value,
                'points_redemption_minimum':      cfg.points_redemption_minimum,
            },
            'loyalty': {
                'points_balance':  points_balance,
                'points_earned':   account.points_earned,
                'points_redeemed': account.points_redeemed,
            },
        })


class ValidateCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        if not code:
            return Response({'valid': False, 'error': 'No code provided.'})
        try:
            coupon = Coupon.objects.get(code=code)
            valid, reason = coupon.is_valid_for(request.user)
            if valid:
                return Response({'valid': True, 'discount': coupon.discount, 'code': coupon.code})
            return Response({'valid': False, 'error': reason})
        except Coupon.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid coupon code.'})


class LoyaltyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cfg     = PromotionConfig.get()
        account = LoyaltyAccount.for_user(request.user)
        txs     = account.transactions.order_by('-created_at')[:20]
        return Response({
            'points_balance':     account.points_balance,
            'points_earned':      account.points_earned,
            'points_redeemed':    account.points_redeemed,
            'redemption_value':   cfg.points_redemption_value,
            'redemption_minimum': cfg.points_redemption_minimum,
            'transactions': [
                {
                    'type':       t.tx_type,
                    'points':     t.points,
                    'note':       t.note,
                    'created_at': t.created_at,
                }
                for t in txs
            ],
        })


class MyCouponsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        available = Coupon.objects.filter(
            user=request.user, is_active=True,
        ).exclude(usages__user=request.user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        used = CouponUsage.objects.filter(user=request.user).select_related('coupon')
        return Response({
            'available': [
                {
                    'code':       c.code,
                    'discount':   c.discount,
                    'type':       c.coupon_type,
                    'expires_at': c.expires_at,
                }
                for c in available
            ],
            'used': [
                {
                    'code':     u.coupon.code,
                    'discount': u.coupon.discount,
                    'used_at':  u.used_at,
                }
                for u in used
            ],
        })
