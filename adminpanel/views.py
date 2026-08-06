from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, F, DecimalField, ExpressionWrapper, FloatField
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import timedelta
from accounts.models import TraderProfile
from accounts.serializers import AdminUserSerializer, TraderProfileSerializer
from orders.models import Order, ReturnRequest
from cart.models import Cart, CartItem
from payments.models import Payment
from orders.serializers import OrderSerializer
from products.models import Product, ProductImage, UserBehavior, PageView
from products.serializers import ProductListSerializer, ProductSerializer, ProductImageSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.text import slugify
import uuid
from .permissions import IsAdminUser, IsFullAdmin, HasPagePermission
from .models import SiteSettings, NewsletterSubscriber, Employee, ALL_PAGES
import secrets
import string

User = get_user_model()


class AdminStatsView(APIView):
    permission_classes = [IsFullAdmin]

    def get(self, request):
        from django.core.cache import cache
        data = cache.get('admin_stats')
        if data is None:
            data = {
                'total_users': User.objects.filter(is_trader=False, is_staff=False).count(),
                'total_traders': User.objects.filter(is_trader=True).count(),
                'pending_traders': TraderProfile.objects.filter(status='pending').count(),
                'total_orders': Order.objects.count(),
                'total_revenue': Order.objects.aggregate(r=Sum('total_price'))['r'] or 0,
                'total_products': Product.objects.filter(is_active=True).count(),
            }
            cache.set('admin_stats', data, 120)  # 2 minutes
        return Response(data)


class AdminAnalyticsView(APIView):
    permission_classes = [HasPagePermission("analytics")]

    def get(self, request):
        from django.core.cache import cache
        cached = cache.get('admin_analytics')
        if cached is not None:
            return Response(cached)

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

        # ── Customer Analytics ──────────────────────────────────────────
        day180 = now - timedelta(days=180)  # 6 months

        # Total customers (non-trader, non-staff)
        total_customers = User.objects.filter(is_trader=False, is_staff=False).count()

        # New customers last 30d
        new_customers_30d = User.objects.filter(
            is_trader=False, is_staff=False, date_joined__gte=day30
        ).count()

        # Active customers: placed at least one order in last 30d
        active_customers_30d = (
            Order.objects
            .filter(created_at__gte=day30)
            .values('user_id')
            .distinct()
            .count()
        )

        # Returning customers: placed 2+ orders ever
        returning_customers = (
            Order.objects
            .values('user_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gte=2)
            .count()
        )

        # Repeat purchase rate: customers with 2+ orders / customers with any order
        customers_with_orders = (
            Order.objects.values('user_id').distinct().count()
        )
        repeat_purchase_rate = round(
            (returning_customers / customers_with_orders * 100), 1
        ) if customers_with_orders > 0 else 0

        # Customer Retention Rate (30d): customers who ordered in prev 30d AND current 30d
        day60 = now - timedelta(days=60)
        prev_period_customers = set(
            Order.objects
            .filter(created_at__gte=day60, created_at__lt=day30)
            .values_list('user_id', flat=True)
            .distinct()
        )
        retained = (
            Order.objects
            .filter(created_at__gte=day30, user_id__in=prev_period_customers)
            .values('user_id').distinct().count()
        ) if prev_period_customers else 0
        retention_rate = round(
            (retained / len(prev_period_customers) * 100), 1
        ) if prev_period_customers else 0

        # CLV: avg total spend per customer who has ever ordered
        clv_data = (
            Order.objects
            .exclude(status__in=['cancelled', 'refunded'])
            .values('user_id')
            .annotate(total_spent=Sum('total_price'))
            .aggregate(avg_clv=Avg('total_spent'))
        )
        clv = float(clv_data['avg_clv'] or 0)

        # CAC proxy: avg revenue per new customer (no ad spend tracked)
        # = total revenue last 30d / new customers last 30d
        revenue_30d_val = float(
            Order.objects.filter(created_at__gte=day30)
            .exclude(status__in=['cancelled', 'refunded'])
            .aggregate(r=Sum('total_price'))['r'] or 0
        )
        cac = round(revenue_30d_val / new_customers_30d, 2) if new_customers_30d > 0 else 0

        # Customers by location (city)
        customers_by_city = list(
            User.objects
            .filter(is_trader=False, is_staff=False)
            .exclude(city='').exclude(city__isnull=True)
            .values('city')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Customers by country
        customers_by_country = list(
            User.objects
            .filter(is_trader=False, is_staff=False)
            .exclude(country='').exclude(country__isnull=True)
            .values('country')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Monthly customer growth: new + returning per month for last 6 months
        new_by_month = list(
            User.objects
            .filter(is_trader=False, is_staff=False, date_joined__gte=day180)
            .annotate(month=TruncMonth('date_joined'))
            .values('month')
            .annotate(new=Count('id'))
            .order_by('month')
        )
        # Active (ordered) per month last 6 months
        active_by_month = list(
            Order.objects
            .filter(created_at__gte=day180)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(active=Count('user_id', distinct=True))
            .order_by('month')
        )
        # Merge into combined monthly list
        month_map = {}
        for r in new_by_month:
            key = str(r['month'])[:7]
            month_map.setdefault(key, {'month': key, 'new': 0, 'active': 0})
            month_map[key]['new'] = r['new']
        for r in active_by_month:
            key = str(r['month'])[:7]
            month_map.setdefault(key, {'month': key, 'new': 0, 'active': 0})
            month_map[key]['active'] = r['active']
        customer_growth_by_month = sorted(month_map.values(), key=lambda x: x['month'])

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

        # Funnel & Conversion analytics (last 30 days)
        # Real funnel logic:
        # pending   = order placed, money NOT yet received (user checked out)
        # confirmed = admin confirmed = money received
        # delivered = order completed

        def pct(num, den):
            return round((num / den) * 100, 1) if den > 0 else 0

        # Step 1: Visitors — distinct sessions on any page
        visitors_30d = (
            PageView.objects
            .filter(created_at__gte=day30)
            .values('session_key')
            .distinct()
            .count()
        )

        # Step 2: Product views — distinct sessions that viewed a product
        product_viewers_30d = (
            UserBehavior.objects
            .filter(created_at__gte=day30)
            .values('session_key')
            .distinct()
            .count()
        )

        # Step 3: Add to Cart — distinct users who have/had cart items in 30d
        add_to_cart_sessions = (
            Cart.objects
            .filter(updated_at__gte=day30, items__isnull=False)
            .values('user_id')
            .distinct()
            .count()
        )

        # Step 4: Checkout = orders placed (ALL statuses — placing an order = checked out)
        orders_placed_30d = Order.objects.filter(created_at__gte=day30).count()

        # Step 5: Payment received = admin confirmed order (confirmed/shipped/pickup/delivered)
        # pending = placed but money not yet received; confirmed = admin received money
        payment_received_30d = (
            Order.objects
            .filter(created_at__gte=day30, status__in=['confirmed', 'shipped', 'pickup', 'delivered'])
            .count()
        )

        # Step 6: Delivered = fully completed
        delivered_30d = (
            Order.objects
            .filter(created_at__gte=day30, status='delivered')
            .count()
        )

        # Pending = placed but not yet confirmed (money not received)
        pending_orders_30d = (
            Order.objects
            .filter(created_at__gte=day30, status='pending')
            .count()
        )

        # Searches
        search_sessions_30d = (
            PageView.objects
            .filter(created_at__gte=day30, path__icontains='/search')
            .values('session_key')
            .distinct()
            .count()
        )
        total_searches_30d = (
            PageView.objects
            .filter(created_at__gte=day30, path__icontains='/search')
            .count()
        )

        # Rates
        # Add-to-cart rate: of product viewers, how many added to cart
        add_to_cart_rate = pct(add_to_cart_sessions, product_viewers_30d)

        # Cart abandonment: had items in cart but never placed an order
        cart_abandonment_rate = pct(
            max(add_to_cart_sessions - orders_placed_30d, 0),
            add_to_cart_sessions
        )

        # Checkout abandonment: placed order (pending) but admin never confirmed (no payment)
        checkout_abandonment_rate = pct(pending_orders_30d, orders_placed_30d)

        # Conversion rate: visitors who got to delivered
        conversion_rate = pct(delivered_30d, visitors_30d)

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

        result = {
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
            'customer_analytics': {
                'total_customers': total_customers,
                'new_customers_30d': new_customers_30d,
                'active_customers_30d': active_customers_30d,
                'returning_customers': returning_customers,
                'repeat_purchase_rate': repeat_purchase_rate,
                'retention_rate': retention_rate,
                'clv': clv,
                'cac': cac,
                'by_city': customers_by_city,
                'by_country': customers_by_country,
                'growth_by_month': customer_growth_by_month,
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
            'funnel_analytics': {
                'visitors_30d': visitors_30d,
                'product_viewers_30d': product_viewers_30d,
                'add_to_cart_sessions': add_to_cart_sessions,
                'orders_placed_30d': orders_placed_30d,
                'payment_received_30d': payment_received_30d,
                'delivered_30d': delivered_30d,
                'pending_orders_30d': pending_orders_30d,
                'search_sessions_30d': search_sessions_30d,
                'total_searches_30d': total_searches_30d,
                'add_to_cart_rate': add_to_cart_rate,
                'cart_abandonment_rate': cart_abandonment_rate,
                'checkout_abandonment_rate': checkout_abandonment_rate,
                'conversion_rate': conversion_rate,
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
        }
        cache.set('admin_analytics', result, 300)  # 5 minutes
        return Response(result)


class AdminUserListView(generics.ListAPIView):
    permission_classes = [HasPagePermission("users")]
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
    permission_classes = [HasPagePermission("users")]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('trader_profile').all()


class AdminTraderListView(generics.ListAPIView):
    permission_classes = [HasPagePermission("traders")]
    serializer_class = TraderProfileSerializer

    def get_queryset(self):
        qs = TraderProfile.objects.select_related('user').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminTraderApproveView(APIView):
    permission_classes = [HasPagePermission("traders")]

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
    permission_classes = [HasPagePermission("orders")]
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related('user').prefetch_related('items__product__images', 'return_requests').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [HasPagePermission("orders")]
    serializer_class = OrderSerializer
    queryset = Order.objects.select_related('user').prefetch_related('items__product__images', 'return_requests').all()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class AdminOrderStatusUpdateView(APIView):
    """Admin-only endpoint to change an order's status."""
    permission_classes = [HasPagePermission("orders")]

    def post(self, request, pk):
        try:
            order = Order.objects.select_related('user').prefetch_related('items__product__images', 'return_requests').get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({'error': f'Invalid status. Valid: {valid_statuses}'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save()
        return Response(OrderSerializer(order, context={'request': request}).data)


class AdminOrderLookupView(APIView):
    """Lookup an order by its order_number prefix (first 8 chars) or full UUID."""
    permission_classes = [HasPagePermission("orders")]

    def get(self, request):
        order_number = request.query_params.get('order_number', '').strip().lstrip('#')
        if not order_number:
            return Response({'error': 'order_number query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = Order.objects.select_related('user').prefetch_related('items__product__images', 'return_requests')
        try:
            order = qs.get(order_number__icontains=order_number)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Order.MultipleObjectsReturned:
            orders = qs.filter(order_number__icontains=order_number)
            return Response(OrderSerializer(orders, many=True, context={'request': request}).data)

        return Response(OrderSerializer(order, context={'request': request}).data)


class AdminProductListView(generics.ListAPIView):
    permission_classes = [HasPagePermission("products")]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return Product.objects.select_related('brand', 'category', 'seller').prefetch_related('images').order_by('-created_at')


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [HasPagePermission("products")]
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
    permission_classes = [HasPagePermission("products")]
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
    permission_classes = [HasPagePermission("products")]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.is_active = not product.is_active
        product.save()
        return Response({'id': product.id, 'is_active': product.is_active})


class AdminResetPasswordView(APIView):
    permission_classes = [HasPagePermission("users")]

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
        from django.core.cache import cache
        data = cache.get('site_settings')
        if data is None:
            s = SiteSettings.get()
            data = {'seller_registration_open': s.seller_registration_open}
            cache.set('site_settings', data, 300)  # 5 minutes
        return Response(data)

    def patch(self, request):
        from django.core.cache import cache
        s = SiteSettings.get()
        val = request.data.get('seller_registration_open')
        if val is None:
            return Response({'error': 'seller_registration_open required.'}, status=status.HTTP_400_BAD_REQUEST)
        s.seller_registration_open = bool(val)
        s.save()
        cache.delete('site_settings')  # invalidate on update
        return Response({'seller_registration_open': s.seller_registration_open})



def _generate_temp_password():
    """Generate a 12-char password with letters, digits, and symbols."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pw = ''.join(secrets.choice(alphabet) for _ in range(12))
        # Ensure at least one of each required type
        if (any(c.islower() for c in pw) and
                any(c.isupper() for c in pw) and
                any(c.isdigit() for c in pw) and
                any(c in "!@#$%^&*()-_=+" for c in pw)):
            return pw


class EmployeeListCreateView(APIView):
    permission_classes = [IsFullAdmin]

    def get(self, request):
        employees = Employee.objects.select_related('user', 'added_by').all().order_by('-created_at')
        data = [
            {
                'id': e.id,
                'user_id': e.user.id,
                'phone': e.user.phone,
                'first_name': e.user.first_name,
                'last_name': e.user.last_name,
                'avatar': e.user.avatar.url if e.user.avatar and e.user.avatar.name else None,
                'permissions': e.permissions,
                'must_change_password': e.must_change_password,
                'added_by': e.added_by.phone if e.added_by else None,
                'created_at': e.created_at,
                'is_active': e.user.is_active,
            }
            for e in employees
        ]
        return Response({'employees': data, 'all_pages': ALL_PAGES})

    def post(self, request):
        phone = (request.data.get('phone') or '').strip()
        permissions = request.data.get('permissions', [])
        first_name = (request.data.get('first_name') or '').strip()

        if not phone:
            return Response({'error': 'Phone number is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(permissions, list) or not permissions:
            return Response({'error': 'At least one permission is required.'}, status=status.HTTP_400_BAD_REQUEST)
        invalid = [p for p in permissions if p not in ALL_PAGES]
        if invalid:
            return Response({'error': f'Invalid permissions: {invalid}'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        existing_user = User.objects.filter(phone=phone).first()
        if existing_user:
            if hasattr(existing_user, 'employee_profile'):
                return Response({'error': 'This phone number is already an employee.'}, status=status.HTTP_400_BAD_REQUEST)
            if existing_user.is_admin or existing_user.is_staff:
                return Response({'error': 'This user is already an admin.'}, status=status.HTTP_400_BAD_REQUEST)

        temp_pw = _generate_temp_password()

        if existing_user:
            user = existing_user
        else:
            user = User(
                phone=phone,
                username=f"emp_{phone}",
                email=None,
                first_name=first_name or phone,
            )
            user.set_password(temp_pw)
            user.save()

        # Mark as staff so IsAdminUser passes for their permitted pages
        user.is_staff = True
        user.set_password(temp_pw)
        user.save(update_fields=['is_staff', 'password'])

        employee = Employee.objects.create(
            user=user,
            added_by=request.user,
            permissions=permissions,
            must_change_password=True,
            temp_password=temp_pw,
        )

        return Response({
            'id': employee.id,
            'phone': user.phone,
            'first_name': user.first_name,
            'permissions': employee.permissions,
            'temp_password': temp_pw,  # shown once to admin
            'must_change_password': True,
        }, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsFullAdmin]

    def patch(self, request, pk):
        try:
            employee = Employee.objects.select_related('user').get(pk=pk)
        except Employee.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        permissions = request.data.get('permissions')
        if permissions is not None:
            invalid = [p for p in permissions if p not in ALL_PAGES]
            if invalid:
                return Response({'error': f'Invalid permissions: {invalid}'}, status=status.HTTP_400_BAD_REQUEST)
            employee.permissions = permissions
            employee.save(update_fields=['permissions'])

        return Response({'id': employee.id, 'permissions': employee.permissions})

    def delete(self, request, pk):
        try:
            employee = Employee.objects.select_related('user').get(pk=pk)
        except Employee.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = employee.user
        user.is_staff = False
        user.save(update_fields=['is_staff'])
        employee.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeSetPasswordView(APIView):
    """Called by the employee on first login to set their own permanent password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response({'error': 'Not an employee account.'}, status=status.HTTP_403_FORBIDDEN)

        if not employee.must_change_password:
            return Response({'error': 'Password already set.'}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get('new_password', '').strip()
        confirm = request.data.get('confirm_password', '').strip()

        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_password != confirm:
            return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save()
        employee.must_change_password = False
        employee.temp_password = ''
        employee.save(update_fields=['must_change_password', 'temp_password'])

        return Response({'message': 'Password updated. You can now access your dashboard.'})
