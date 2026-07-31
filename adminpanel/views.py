from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from accounts.models import TraderProfile
from accounts.serializers import AdminUserSerializer, TraderProfileSerializer
from orders.models import Order, ReturnRequest
from orders.serializers import OrderSerializer
from products.models import Product, ProductImage, UserBehavior, PageView
from products.serializers import ProductListSerializer, ProductSerializer, ProductImageSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.text import slugify
import uuid
from .permissions import IsAdminUser
from .models import SiteSettings, NewsletterSubscriber

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


class AdminAnalyticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        day30 = now - timedelta(days=30)
        day7  = now - timedelta(days=7)
        day1  = now - timedelta(days=1)

        # ── User stats ──────────────────────────────────────────────────
        total_users    = User.objects.filter(is_staff=False).count()
        new_30d        = User.objects.filter(date_joined__gte=day30, is_staff=False).count()
        new_7d         = User.objects.filter(date_joined__gte=day7,  is_staff=False).count()
        new_24h        = User.objects.filter(date_joined__gte=day1,  is_staff=False).count()
        traders        = User.objects.filter(is_trader=True).count()
        customers      = User.objects.filter(is_trader=False, is_staff=False).count()

        # Signups per day (last 30 days)
        signups_by_day = (
            User.objects
            .filter(date_joined__gte=day30, is_staff=False)
            .extra(select={'day': "date(date_joined)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        # ── Geography ───────────────────────────────────────────────────
        cities = (
            User.objects
            .filter(is_staff=False)
            .exclude(city__isnull=True).exclude(city='')
            .values('city')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # ── Orders ──────────────────────────────────────────────────────
        orders_30d = Order.objects.filter(created_at__gte=day30)
        orders_by_day = (
            orders_30d
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(count=Count('id'), revenue=Sum('total_price'))
            .order_by('day')
        )
        returning_users = (
            Order.objects
            .values('user_id')
            .annotate(order_count=Count('id'))
            .filter(order_count__gt=1)
            .count()
        )

        # ── Product behavior ────────────────────────────────────────────
        # Most viewed products (by event count)
        most_viewed = (
            UserBehavior.objects
            .filter(created_at__gte=day30)
            .values('product__id', 'product__name', 'product__slug')
            .annotate(views=Count('id'), total_seconds=Sum('seconds_spent'))
            .order_by('-views')[:10]
        )

        # Most time spent on products
        most_time = (
            UserBehavior.objects
            .filter(created_at__gte=day30)
            .values('product__id', 'product__name', 'product__slug')
            .annotate(total_seconds=Sum('seconds_spent'), views=Count('id'))
            .order_by('-total_seconds')[:10]
        )

        # Most viewed categories
        top_categories = (
            UserBehavior.objects
            .filter(created_at__gte=day30, category__isnull=False)
            .values('category__name')
            .annotate(views=Count('id'))
            .order_by('-views')[:8]
        )

        # Most viewed brands
        top_brands = (
            UserBehavior.objects
            .filter(created_at__gte=day30, brand__isnull=False)
            .values('brand__name')
            .annotate(views=Count('id'))
            .order_by('-views')[:8]
        )

        # Avg session time (seconds) per day
        avg_time_by_day = (
            UserBehavior.objects
            .filter(created_at__gte=day30)
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(avg_seconds=Avg('seconds_spent'), sessions=Count('session_key', distinct=True))
            .order_by('day')
        )

        # Active sessions today
        active_today = (
            UserBehavior.objects
            .filter(created_at__gte=day1)
            .values('session_key')
            .distinct()
            .count()
        )

        COMMISSION_RATE = Product.COMMISSION_RATE
        commission_expr = ExpressionWrapper(
            F('items__product__trader_price') * F('items__quantity') * COMMISSION_RATE,
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
        delivery_expr = ExpressionWrapper(
            F('items__product__delivery_charge') * F('items__quantity'),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
        commission_earned = float(
            orders_30d.filter(items__product__trader_price__isnull=False)
            .aggregate(total=Sum(commission_expr))['total'] or 0
        )
        delivery_fees_collected = float(
            orders_30d.filter(items__product__isnull=False)
            .aggregate(total=Sum(delivery_expr))['total'] or 0
        )
        revenue_by_day = (
            orders_30d
            .filter(items__product__trader_price__isnull=False)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(commission=Sum(commission_expr), delivery=Sum(delivery_expr))
            .order_by('day')
        )
        revenue_by_day_list = [
            {'day': str(r['day']), 'commission': float(r['commission'] or 0), 'delivery': float(r['delivery'] or 0)}
            for r in revenue_by_day
        ]

        # Top pages by views and time spent
        top_pages = (
            PageView.objects
            .filter(created_at__gte=day30)
            .values('path')
            .annotate(views=Count('id'), total_seconds=Sum('seconds_spent'))
            .order_by('-views')[:15]
        )

        # Avg time per page
        avg_time_per_page = (
            PageView.objects
            .filter(created_at__gte=day30)
            .values('path')
            .annotate(avg_seconds=Avg('seconds_spent'), views=Count('id'))
            .order_by('-avg_seconds')[:10]
        )

        # Returns analytics
        # 1. Orders not picked up: status='pickup' (awaiting collection)
        not_picked_up = Order.objects.filter(status='pickup').count()
        not_picked_up_30d = Order.objects.filter(status='pickup', created_at__gte=day30).count()

        # 2. Cancelled orders (includes those abandoned at pickup)
        cancelled_total = Order.objects.filter(status='cancelled').count()
        cancelled_30d = Order.objects.filter(status='cancelled', created_at__gte=day30).count()

        # 3. User return requests
        return_requests_total = ReturnRequest.objects.count()
        return_requests_30d = ReturnRequest.objects.filter(created_at__gte=day30).count()

        # By status
        returns_by_status = list(
            ReturnRequest.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )

        # By reason
        returns_by_reason = list(
            ReturnRequest.objects
            .values('reason')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Daily return requests (last 30d)
        returns_by_day = list(
            ReturnRequest.objects
            .filter(created_at__gte=day30)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        returns_by_day = [{'day': str(r['day']), 'count': r['count']} for r in returns_by_day]

        # Most ordered products
        most_ordered = (
            Order.objects
            .filter(created_at__gte=day30)
            .values('items__product_name')
            .annotate(orders=Count('items__id'), revenue=Sum(F('items__product_price') * F('items__quantity')))
            .exclude(items__product_name=None)
            .order_by('-orders')[:10]
        )

        return Response({
            'users': {
                'total': total_users,
                'customers': customers,
                'traders': traders,
                'new_30d': new_30d,
                'new_7d': new_7d,
                'new_24h': new_24h,
                'returning': returning_users,
                'signups_by_day': list(signups_by_day),
            },
            'geography': {
                'top_cities': list(cities),
            },
            'orders': {
                'total_30d': orders_30d.count(),
                'revenue_30d': float(orders_30d.aggregate(r=Sum('total_price'))['r'] or 0),
                'commission_earned': commission_earned,
                'delivery_fees_collected': delivery_fees_collected,
                'by_day': list(orders_by_day),
                'revenue_by_day': revenue_by_day_list,
            },
            'returns_analytics': {
                'not_picked_up': not_picked_up,
                'not_picked_up_30d': not_picked_up_30d,
                'cancelled_total': cancelled_total,
                'cancelled_30d': cancelled_30d,
                'return_requests_total': return_requests_total,
                'return_requests_30d': return_requests_30d,
                'by_status': returns_by_status,
                'by_reason': returns_by_reason,
                'by_day': returns_by_day,
            },
            'behavior': {
                'active_sessions_today': active_today,
                'most_viewed_products': list(most_viewed),
                'most_time_products': list(most_time),
                'top_categories': list(top_categories),
                'top_brands': list(top_brands),
                'avg_time_by_day': list(avg_time_by_day),
                'most_ordered_products': list(most_ordered),
                'top_pages': list(top_pages),
                'avg_time_per_page': list(avg_time_per_page),
            },
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
            profile = TraderProfile.objects.select_related('user').get(pk=pk)
        except TraderProfile.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        action = request.data.get('action')
        if action == 'approve':
            profile.status = TraderProfile.STATUS_APPROVED
            profile.user.is_active = True
            profile.user.save(update_fields=['is_active'])
            profile.save()
        elif action == 'reject':
            profile.status = TraderProfile.STATUS_REJECTED
            profile.save()
        elif action == 'deactivate':
            profile.status = TraderProfile.STATUS_REJECTED
            profile.user.is_active = False
            profile.user.save(update_fields=['is_active'])
            profile.save()
        elif action == 'ban':
            profile.status = TraderProfile.STATUS_REJECTED
            profile.user.is_active = False
            profile.user.is_trader = False
            profile.user.save(update_fields=['is_active', 'is_trader'])
            profile.save()
        elif action == 'delete':
            profile.user.delete()  # cascades to profile
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
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


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.select_related('brand', 'category', 'seller').prefetch_related('images').all()

    def perform_update(self, serializer):
        name = self.request.data.get('name', serializer.instance.name)
        if name != serializer.instance.name:
            uid = str(uuid.uuid4())[:8]
            new_slug = slugify(name) + '-' + uid
            while Product.objects.filter(slug=new_slug).exclude(pk=serializer.instance.pk).exists():
                new_slug = slugify(name) + '-' + str(uuid.uuid4())[:8]
            serializer.save(slug=new_slug)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class AdminProductImageView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'No image provided.'}, status=status.HTTP_400_BAD_REQUEST)
        is_primary = not product.images.exists()
        img = ProductImage.objects.create(product=product, image=image, is_primary=is_primary)
        return Response(ProductImageSerializer(img).data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        image_id = request.data.get('image_id')
        try:
            img = ProductImage.objects.get(id=image_id, product_id=pk)
        except ProductImage.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        img.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class AdminResetPasswordView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        new_password = request.data.get('new_password', '').strip()
        if len(new_password) < 6:
            return Response({'error': 'Password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'message': f'Password reset for {user.email}.'})


class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        _, created = NewsletterSubscriber.objects.get_or_create(email=email)
        if not created:
            return Response({'detail': 'already_subscribed'}, status=status.HTTP_200_OK)
        return Response({'detail': 'subscribed'}, status=status.HTTP_201_CREATED)


class SiteSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        s = SiteSettings.get()
        return Response({'seller_registration_open': s.seller_registration_open})

    def patch(self, request):
        s = SiteSettings.get()
        val = request.data.get('seller_registration_open')
        if val is None:
            return Response({'error': 'seller_registration_open required.'}, status=status.HTTP_400_BAD_REQUEST)
        s.seller_registration_open = bool(val)
        s.save()
        return Response({'seller_registration_open': s.seller_registration_open})

