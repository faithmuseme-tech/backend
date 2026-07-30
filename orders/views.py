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


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.filter(user=self.request.user).prefetch_related('items__product__images')
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
        return Order.objects.filter(user=self.request.user).prefetch_related('items__product__images')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload_items = data.pop('items', [])

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
            subtotal = sum(item.subtotal for item in cart_items)
            delivery_items = cart_items
        else:
            subtotal = sum(
                item['product_price'] * item['quantity'] for item in payload_items
            )
            delivery_items = payload_items

        delivery_fee = calculate_delivery_fee(shipping_city, delivery_items)
        total = subtotal + delivery_fee

        order = Order.objects.create(
            user=request.user,
            total_price=total,
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

        try:
            order = Order.objects.get(id=d['order_id'], user=request.user, status='delivered')
        except Order.DoesNotExist:
            return Response({'error': 'Order not found or not eligible for return.'}, status=status.HTTP_400_BAD_REQUEST)

        if ReturnRequest.objects.filter(order=order, user=request.user).exists():
            return Response({'error': 'A return request for this order already exists.'}, status=status.HTTP_400_BAD_REQUEST)

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
