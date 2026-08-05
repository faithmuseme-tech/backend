from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, F
from .models import Order, OrderItem, ReturnRequest
from .serializers import (
    OrderSerializer, CreateOrderSerializer, calculate_delivery_fee, get_zone_fee,
    ReturnRequestSerializer, ReturnRequestCreateSerializer, ReturnRequestAdminSerializer,
)
from cart.models import Cart
from products.models import Product
from adminpanel.permissions import IsAdminUser
from notifications.models import Notification
from coupons.models import Coupon, CouponUsage, LoyaltyAccount, LoyaltyTransaction, PromotionConfig


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.filter(user=self.request.user).prefetch_related('items__product__images', 'return_requests')
        order_number = self.request.query_params.get('order_number')
        if order_number:
            qs = qs.filter(order_number=order_number)
        return qs

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items__product__images', 'return_requests')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload_items = data.pop('items', [])
        coupon_code = (data.get('coupon_code') or '').strip().upper()
        redeem_points = data.get('redeem_points', False)

        shipping_address = data.get('shipping_address') or request.user.address or ''
        shipping_city = data.get('shipping_city') or request.user.city or ''
        shipping_country = data.get('shipping_country') or request.user.country or 'Uganda'
        shipping_zip = data.get('shipping_zip') or request.user.zip_code or ''

        # Try backend cart first, fall back to payload items
        cart_items = []
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = list(cart.items.select_related('product').all())
        except Cart.DoesNotExist:
            pass

        if not cart_items and not payload_items:
            return Response({'error': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        if cart_items:
            subtotal = int(sum(item.subtotal for item in cart_items))
            delivery_items = cart_items
        else:
            subtotal = int(sum(
                item['product_price'] * item['quantity'] for item in payload_items
            ))
            delivery_items = payload_items

        delivery_fee = calculate_delivery_fee(shipping_city, delivery_items)

        # ── Server-side coupon validation ──────────────────────────────────
        cfg = PromotionConfig.get()
        coupon_discount = 0
        coupon_obj = None
        if coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code=coupon_code)
                valid, reason = coupon_obj.is_valid_for(request.user)
                if not valid:
                    return Response({'error': reason}, status=status.HTTP_400_BAD_REQUEST)
                coupon_discount = coupon_obj.discount
            except Coupon.DoesNotExist:
                return Response({'error': 'Invalid coupon code.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Server-side loyalty points validation ──────────────────────────
        points_discount = 0
        points_used = 0
        loyalty_account = None
        if redeem_points:
            loyalty_account = LoyaltyAccount.for_user(request.user)
            if loyalty_account.points_balance < cfg.points_redemption_minimum:
                return Response(
                    {'error': f'You need at least {cfg.points_redemption_minimum} points to redeem.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            points_used = loyalty_account.points_balance
            points_discount = min(points_used * cfg.points_redemption_value, subtotal)

        coupon_discount = min(coupon_discount, subtotal + delivery_fee)
        grand_total = max(0, subtotal + delivery_fee - coupon_discount - points_discount)

        order = Order.objects.create(
            user=request.user,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            coupon_discount=coupon_discount,
            points_discount=points_discount,
            coupon_code_used=coupon_code,
            points_used=points_used,
            total_price=grand_total,
            shipping_address=shipping_address,
            shipping_city=shipping_city,
            shipping_country=shipping_country,
            shipping_zip=shipping_zip,
            notes=data.get('notes', ''),
        )

        if cart_items:
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.price,
                    quantity=item.quantity,
                    selected_options=item.selected_options or {},
                )
                p = item.product
                p.stock = max(0, p.stock - item.quantity)
                p.save(update_fields=['stock', 'is_active'])
            cart.items.all().delete()
        else:
            for item in payload_items:
                product = None
                if item.get('product_id'):
                    product = Product.objects.filter(id=item['product_id']).first()
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=item['product_name'],
                    product_price=item['product_price'],
                    quantity=item['quantity'],
                )
                if product:
                    product.stock = max(0, product.stock - item['quantity'])
                    product.save(update_fields=['stock', 'is_active'])

        # ── Record coupon usage ────────────────────────────────────────────
        if coupon_obj:
            coupon_obj.times_used += 1
            coupon_obj.save(update_fields=['times_used'])
            CouponUsage.objects.create(coupon=coupon_obj, user=request.user, order_id=order.id)

        # ── Deduct loyalty points ──────────────────────────────────────────
        if points_used > 0 and loyalty_account:
            loyalty_account.points_balance = max(0, loyalty_account.points_balance - points_used)
            loyalty_account.points_redeemed += points_used
            loyalty_account.save(update_fields=['points_balance', 'points_redeemed', 'updated_at'])
            LoyaltyTransaction.objects.create(
                account=loyalty_account, order_id=order.id,
                tx_type=LoyaltyTransaction.TYPE_REDEEM, points=-points_used,
                note=f'Redeemed {points_used} pts for UGX {points_discount:,} discount on order #{str(order.order_number)[:8].upper()}'
            )

        from products.views import clear_product_caches
        clear_product_caches()

        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)


class TraderOrderListView(generics.ListAPIView):
    """Orders containing at least one product belonging to the requesting trader."""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(items__product__seller=self.request.user)
            .distinct()
            .prefetch_related('items__product__images')
            .select_related('user')
            .order_by('-created_at')
        )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class TraderStatsView(APIView):
    """Revenue and sales stats for the requesting trader."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        trader_items = OrderItem.objects.filter(product__seller=request.user)
        revenue = trader_items.aggregate(
            total=Sum(F('product_price') * F('quantity'))
        )['total'] or 0
        products_sold = trader_items.aggregate(total=Sum('quantity'))['total'] or 0
        orders_count = (
            Order.objects.filter(items__product__seller=request.user).distinct().count()
        )
        return Response({
            'revenue': revenue,
            'products_sold': products_sold,
            'orders_count': orders_count,
        })


class ReturnRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ReturnRequestCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        # 1. User must have at least one order
        if not Order.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'no_orders', 'detail': 'You have not placed any orders yet.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Order must exist, belong to user, and be delivered
        try:
            order = Order.objects.get(id=d['order_id'], user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'order_not_found', 'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.status != 'delivered':
            return Response(
                {'error': 'not_delivered', 'detail': f'Order is currently "{order.status}". Only delivered orders are eligible for a return.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 3. No duplicate return request
        if ReturnRequest.objects.filter(order=order, user=request.user).exists():
            return Response(
                {'error': 'duplicate_return', 'detail': 'A return request for this order already exists.'},
                status=status.HTTP_409_CONFLICT
            )

        rr = ReturnRequest.objects.create(
            order=order, user=request.user,
            reason=d['reason'], description=d['description'],
        )
        if d['item_ids']:
            items = OrderItem.objects.filter(id__in=d['item_ids'], order=order)
            rr.items.set(items)

        return Response(ReturnRequestSerializer(rr).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        qs = ReturnRequest.objects.filter(user=request.user).select_related('order').prefetch_related('items')
        return Response(ReturnRequestSerializer(qs, many=True).data)


class AdminReturnRequestListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ReturnRequestAdminSerializer

    def get_queryset(self):
        qs = ReturnRequest.objects.select_related('order', 'user').prefetch_related('items').all()
        s = self.request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)
        return qs


class AdminReturnRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ReturnRequestAdminSerializer
    queryset = ReturnRequest.objects.select_related('order', 'user').prefetch_related('items').all()

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        rr = serializer.save()
        new_status = rr.status

        if new_status != old_status:
            STATUS_MESSAGES = {
                'approved':  (
                    'Return Request Approved',
                    f'Your return request for order #{str(rr.order.order_number)[:8].upper()} has been approved. '
                    f'Please bring the item(s) to our location or await further instructions.'
                ),
                'rejected':  (
                    'Return Request Rejected',
                    f'Your return request for order #{str(rr.order.order_number)[:8].upper()} has been reviewed '
                    f'and unfortunately does not meet our return criteria.'
                ),
                'completed': (
                    'Return Completed',
                    f'Your return for order #{str(rr.order.order_number)[:8].upper()} has been completed '
                    f'and your refund is being processed.'
                ),
                'pending':   (
                    'Return Request Received',
                    f'We have received your return request for order #{str(rr.order.order_number)[:8].upper()} '
                    f'and will review it shortly.'
                ),
            }
            title, message = STATUS_MESSAGES.get(new_status, ('Return Update', 'Your return request has been updated.'))
            if rr.admin_notes:
                message += f'\n\nAdmin note: {rr.admin_notes}'
            Notification.objects.create(
                user=rr.user,
                type=Notification.TYPE_RETURN_UPDATE,
                title=title,
                message=message,
                order_id=rr.order.id,
            )
