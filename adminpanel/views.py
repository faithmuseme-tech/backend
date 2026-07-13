from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from accounts.models import TraderProfile
from accounts.serializers import AdminUserSerializer, TraderProfileSerializer
from orders.models import Order
from orders.serializers import OrderSerializer
from products.models import Product
from products.serializers import ProductListSerializer
from .permissions import IsAdminUser

User = get_user_model()


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            'total_users': User.objects.filter(is_trader=False, is_staff=False).count(),
            'total_traders': User.objects.filter(is_trader=True).count(),
            'pending_traders': TraderProfile.objects.filter(status='pending').count(),
            'total_orders': Order.objects.count(),
            'total_revenue': Order.objects.aggregate(r=Sum('total_price'))['r'] or 0,
            'total_products': Product.objects.filter(is_active=True).count(),
        })


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        qs = User.objects.select_related('trader_profile').order_by('-date_joined')
        role = self.request.query_params.get('role')
        if role == 'trader':
            qs = qs.filter(is_trader=True)
        elif role == 'customer':
            qs = qs.filter(is_trader=False, is_staff=False, is_admin=False)
        return qs


class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('trader_profile').all()


class AdminTraderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TraderProfileSerializer

    def get_queryset(self):
        qs = TraderProfile.objects.select_related('user').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminTraderApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            profile = TraderProfile.objects.get(pk=pk)
        except TraderProfile.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        action = request.data.get('action')
        if action == 'approve':
            profile.status = TraderProfile.STATUS_APPROVED
        elif action == 'reject':
            profile.status = TraderProfile.STATUS_REJECTED
        else:
            return Response({'error': 'Invalid action. Use approve or reject.'}, status=status.HTTP_400_BAD_REQUEST)
        profile.save()
        return Response(TraderProfileSerializer(profile).data)


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = OrderSerializer
    queryset = Order.objects.select_related('user').prefetch_related('items').all()


class AdminOrderStatusUpdateView(APIView):
    """Admin-only endpoint to change an order's status."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({'error': f'Invalid status. Valid: {valid_statuses}'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save()
        return Response(OrderSerializer(order).data)


class AdminOrderLookupView(APIView):
    """Lookup an order by its order_number prefix (first 8 chars) or full UUID."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        order_number = request.query_params.get('order_number', '').strip().lstrip('#')
        if not order_number:
            return Response({'error': 'order_number query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(order_number__icontains=order_number)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Order.MultipleObjectsReturned:
            # prefix matched multiple — return the list
            orders = Order.objects.filter(order_number__icontains=order_number)
            return Response(OrderSerializer(orders, many=True).data)

        return Response(OrderSerializer(order).data)


class AdminProductListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return Product.objects.select_related('brand', 'category', 'seller').prefetch_related('images').order_by('-created_at')


class AdminProductToggleView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.is_active = not product.is_active
        product.save()
        return Response({'id': product.id, 'is_active': product.is_active})
