"""
Insights engine — generates smart, data-driven insights for the admin dashboard.
Each insight has: type, severity, title, detail, metric, recommended_actions.
"""
from django.utils import timezone
from django.db.models import (
    Sum, Count, Avg, F, Q, FloatField, DecimalField, ExpressionWrapper
)
from django.db.models.functions import TruncDate, TruncWeek
from datetime import timedelta
from decimal import Decimal


def _pct_change(new, old):
    """Return % change from old to new. None if old is 0."""
    if not old:
        return None
    return round(((new - old) / old) * 100, 1)


def _fmt_ugx(n):
    return f"UGX {int(n or 0):,}"


def generate_insights():
    from django.contrib.auth import get_user_model
    from orders.models import Order, OrderItem
    from products.models import Product, UserBehavior, PageView
    from reviews.models import Review
    from wishlist.models import Wishlist
    from cart.models import Cart, CartItem
    from accounts.models import TraderProfile

    User = get_user_model()
    now = timezone.now()
    day7   = now - timedelta(days=7)
    day14  = now - timedelta(days=14)
    day30  = now - timedelta(days=30)
    day60  = now - timedelta(days=60)
    day90  = now - timedelta(days=90)

    insights = []

    def add(insight_type, severity, title, detail, metric=None, actions=None, data=None):
        insights.append({
            'type': insight_type,
            'severity': severity,   # critical | warning | info | positive
            'title': title,
            'detail': detail,
            'metric': metric,
            'actions': actions or [],
            'data': data or {},
        })

    # ── 1. Revenue Forecast ──────────────────────────────────────────────────
    rev_30d = float(
        Order.objects.filter(created_at__gte=day30, status__in=['confirmed','shipped','pickup','delivered'])
        .aggregate(r=Sum('total_price'))['r'] or 0
    )
    daily_avg = rev_30d / 30
    projected = daily_avg * 30
    add(
        'revenue_forecast', 'info',
        'Revenue Forecast',
        f"Based on the last 30 days (avg {_fmt_ugx(daily_avg)}/day), projected revenue for the next 30 days is {_fmt_ugx(projected)}.",
        metric=f"{_fmt_ugx(projected)} projected",
        actions=[{'label': 'View Analytics', 'href': '/admin/dashboard/analytics'}],
    )

    # ── 2. Sales Drop / Spike per product ───────────────────────────────────
    # Compare orders per product: last 7d vs prev 7d
    curr_week = (
        OrderItem.objects.filter(order__created_at__gte=day7)
        .values('product_name')
        .annotate(qty=Sum('quantity'))
    )
    prev_week = (
        OrderItem.objects.filter(order__created_at__gte=day14, order__created_at__lt=day7)
        .values('product_name')
        .annotate(qty=Sum('quantity'))
    )
    prev_map = {r['product_name']: r['qty'] for r in prev_week}
    weekly_avg_orders = (
        Order.objects.filter(created_at__gte=day30).count() / 4
    ) or 1

    for row in curr_week:
        name = row['product_name']
        curr_qty = row['qty']
        prev_qty = prev_map.get(name, 0)
        chg = _pct_change(curr_qty, prev_qty)
        if chg is None:
            continue
        product = Product.objects.filter(name=name).first()
        pid = product.id if product else None
        if chg <= -20:
            add(
                'sales_drop', 'warning',
                f'Sales Drop: {name}',
                f"{name} sales dropped {abs(chg):.0f}% compared with last week ({prev_qty} → {curr_qty} units).",
                metric=f"{chg:+.0f}% vs last week",
                actions=[
                    {'label': 'View Product', 'href': f'/admin/dashboard/products?id={pid}'},
                    {'label': 'Create Discount', 'href': f'/admin/dashboard/products?discount={pid}'},
                ],
                data={'product_id': pid},
            )
        elif chg >= 40:
            add(
                'sales_spike', 'positive',
                f'Trending: {name}',
                f"{name} sales increased {chg:.0f}% over the last 7 days ({prev_qty} → {curr_qty} units).",
                metric=f"+{chg:.0f}% vs last week",
                actions=[
                    {'label': 'View Product', 'href': f'/admin/dashboard/products?id={pid}'},
                ],
                data={'product_id': pid},
            )

    # ── 3. High Views, Low Sales ─────────────────────────────────────────────
    view_counts = (
        UserBehavior.objects.filter(created_at__gte=day30)
        .values('product__id', 'product__name')
        .annotate(views=Count('id'))
        .order_by('-views')[:20]
    )
    order_counts = {
        r['product_name']: r['qty']
        for r in OrderItem.objects.filter(order__created_at__gte=day30)
        .values('product_name').annotate(qty=Sum('quantity'))
    }
    for row in view_counts:
        views = row['views']
        name = row['product__name']
        pid = row['product__id']
        sales = order_counts.get(name, 0)
        if views >= 100 and sales < views * 0.03:
            add(
                'high_views_low_sales', 'warning',
                f'High Views, Low Sales: {name}',
                f"{name} received {views:,} views but only {sales} purchases in the last 30 days. "
                f"Conversion rate: {round(sales/views*100,1)}%.",
                metric=f"{views:,} views / {sales} sales",
                actions=[
                    {'label': 'View Product', 'href': f'/admin/dashboard/products?id={pid}'},
                    {'label': 'Create Discount', 'href': f'/admin/dashboard/products?discount={pid}'},
                ],
                data={'product_id': pid},
            )

    # ── 4. Stockout Risk ─────────────────────────────────────────────────────
    products_with_stock = Product.objects.filter(is_active=True, stock__gt=0, stock__lte=30)
    for product in products_with_stock[:15]:
        daily_sales = (
            OrderItem.objects.filter(product=product, order__created_at__gte=day30)
            .aggregate(total=Sum('quantity'))['total'] or 0
        ) / 30
        if daily_sales > 0:
            days_left = round(product.stock / daily_sales)
            if days_left <= 10:
                reorder_qty = max(int(daily_sales * 30), 10)
                add(
                    'stockout_risk', 'critical',
                    f'Stockout Risk: {product.name}',
                    f"{product.name} has {product.stock} units remaining. "
                    f"At {daily_sales:.1f} units/day, stock runs out in ~{days_left} days. "
                    f"Recommended reorder: {reorder_qty} units.",
                    metric=f"{days_left} days left",
                    actions=[
                        {'label': 'View Product', 'href': f'/admin/dashboard/products?id={product.id}'},
                        {'label': 'Edit Stock', 'href': f'/admin/dashboard/products?edit={product.id}'},
                    ],
                    data={'product_id': product.id, 'days_left': days_left, 'reorder_qty': reorder_qty},
                )

    # ── 5. Dead Stock ────────────────────────────────────────────────────────
    sold_ids = set(
        OrderItem.objects.filter(order__created_at__gte=day60)
        .values_list('product_id', flat=True).distinct()
    )
    dead_stock = Product.objects.filter(is_active=True, stock__gt=0).exclude(id__in=sold_ids)
    dead_count = dead_stock.count()
    if dead_count > 0:
        names = list(dead_stock.values_list('name', flat=True)[:3])
        add(
            'dead_stock', 'warning',
            f'Dead Stock: {dead_count} Products',
            f"{dead_count} products have had no sales in the last 60 days. "
            f"Examples: {', '.join(names)}{'...' if dead_count > 3 else ''}. "
            f"Consider discounting or removing them.",
            metric=f"{dead_count} products",
            actions=[
                {'label': 'View Products', 'href': '/admin/dashboard/products'},
            ],
        )

    # ── 6. Cart Abandonment Rate ─────────────────────────────────────────────
    carts_with_items = Cart.objects.filter(updated_at__gte=day7, items__isnull=False).values('user_id').distinct().count()
    orders_this_week = Order.objects.filter(created_at__gte=day7).count()
    carts_prev = Cart.objects.filter(updated_at__gte=day14, updated_at__lt=day7, items__isnull=False).values('user_id').distinct().count()
    orders_prev_week = Order.objects.filter(created_at__gte=day14, created_at__lt=day7).count()

    abandon_curr = round((max(carts_with_items - orders_this_week, 0) / carts_with_items * 100), 1) if carts_with_items else 0
    abandon_prev = round((max(carts_prev - orders_prev_week, 0) / carts_prev * 100), 1) if carts_prev else 0
    chg = _pct_change(abandon_curr, abandon_prev)
    if chg and chg >= 5:
        add(
            'cart_abandonment', 'warning',
            'Cart Abandonment Increased',
            f"Cart abandonment increased {chg:.0f}% this week ({abandon_prev}% → {abandon_curr}%). "
            f"{carts_with_items} carts had items but only {orders_this_week} orders were placed.",
            metric=f"{abandon_curr}% abandonment",
            actions=[
                {'label': 'View Analytics', 'href': '/admin/dashboard/analytics'},
            ],
        )

    # ── 7. Customer Churn Risk ───────────────────────────────────────────────
    churn_users = (
        User.objects.filter(is_trader=False, is_staff=False)
        .annotate(last_order=F('orders__created_at'))
        .filter(orders__created_at__gte=day90, orders__created_at__lt=day30)
        .exclude(orders__created_at__gte=day30)
        .values('id').distinct().count()
    )
    if churn_users >= 5:
        add(
            'churn_risk', 'warning',
            'Customer Churn Risk',
            f"{churn_users} previously active customers haven't purchased in 30–90 days and may be churning. "
            f"Consider a re-engagement campaign.",
            metric=f"{churn_users} at-risk customers",
            actions=[
                {'label': 'View Customers', 'href': '/admin/dashboard/users'},
            ],
        )

    # ── 8. High-Value Customers ──────────────────────────────────────────────
    hvc_threshold = 500_000
    hvc = (
        Order.objects.exclude(status__in=['cancelled', 'refunded'])
        .values('user_id')
        .annotate(ltv=Sum('total_price'))
        .filter(ltv__gte=hvc_threshold)
        .count()
    )
    if hvc > 0:
        add(
            'high_value_customers', 'positive',
            'High-Value Customers',
            f"{hvc} customers have generated more than {_fmt_ugx(hvc_threshold)} in lifetime purchases. "
            f"Consider a loyalty programme to retain them.",
            metric=f"{hvc} VIP customers",
            actions=[
                {'label': 'View Customers', 'href': '/admin/dashboard/users'},
            ],
        )

    # ── 9. Repeat Purchase Opportunity ──────────────────────────────────────
    repeat_candidates = (
        Order.objects.filter(created_at__gte=day90, created_at__lt=day60)
        .exclude(status__in=['cancelled', 'refunded'])
        .values('user_id').distinct().count()
    )
    if repeat_candidates >= 10:
        add(
            'repeat_purchase', 'info',
            'Repeat Purchase Opportunity',
            f"{repeat_candidates} customers purchased more than 60 days ago and may be ready for replenishment. "
            f"A targeted reminder could recover this revenue.",
            metric=f"{repeat_candidates} customers",
            actions=[
                {'label': 'View Customers', 'href': '/admin/dashboard/users'},
            ],
        )

    # ── 10. Rating Alert ─────────────────────────────────────────────────────
    # Products whose avg rating this month is significantly lower than overall
    low_rated = (
        Review.objects.filter(created_at__gte=day30)
        .values('product__id', 'product__name')
        .annotate(recent_avg=Avg('rating'), review_count=Count('id'))
        .filter(recent_avg__lte=3.0, review_count__gte=3)
        .order_by('recent_avg')[:5]
    )
    for row in low_rated:
        add(
            'rating_alert', 'warning',
            f"Rating Alert: {row['product__name']}",
            f"{row['product__name']} has an average rating of {row['recent_avg']:.1f} "
            f"from {row['review_count']} reviews this month.",
            metric=f"{row['recent_avg']:.1f} avg rating",
            actions=[
                {'label': 'View Product', 'href': f"/admin/dashboard/products?id={row['product__id']}"},
                {'label': 'View Reviews', 'href': f"/admin/dashboard/products?reviews={row['product__id']}"},
            ],
            data={'product_id': row['product__id']},
        )

    # ── 11. Seller Performance Alert ────────────────────────────────────────
    marketplace_cancel_rate = (
        Order.objects.filter(created_at__gte=day30, status='cancelled').count() /
        max(Order.objects.filter(created_at__gte=day30).count(), 1) * 100
    )
    seller_stats = (
        Order.objects.filter(created_at__gte=day30, items__product__seller__isnull=False)
        .values('items__product__seller__id', 'items__product__seller__email')
        .annotate(
            total=Count('id', distinct=True),
            cancelled=Count('id', distinct=True, filter=Q(status='cancelled')),
        )
        .filter(total__gte=5)
    )
    for row in seller_stats:
        cancel_rate = round(row['cancelled'] / row['total'] * 100, 1)
        if cancel_rate > marketplace_cancel_rate * 2 and cancel_rate > 10:
            seller_id = row['items__product__seller__id']
            seller_email = row['items__product__seller__email']
            add(
                'seller_performance', 'critical',
                f'Seller Performance Alert',
                f"Seller {seller_email} has a {cancel_rate}% cancellation rate "
                f"(marketplace avg: {marketplace_cancel_rate:.1f}%) over the last 30 days.",
                metric=f"{cancel_rate}% cancellation rate",
                actions=[
                    {'label': 'View Seller', 'href': f'/admin/dashboard/traders?id={seller_id}'},
                    {'label': 'View Orders', 'href': f'/admin/dashboard/orders?seller={seller_id}'},
                    {'label': 'Contact Seller', 'href': f'/admin/dashboard/chat'},
                ],
                data={'seller_id': seller_id},
            )

    # ── 12. Wishlist Demand ──────────────────────────────────────────────────
    wishlist_hot = (
        Product.objects.filter(is_active=True)
        .annotate(wish_count=Count('wishlisted_by'))
        .filter(wish_count__gte=5)
        .order_by('-wish_count')[:5]
    )
    for p in wishlist_hot:
        sales_30d = OrderItem.objects.filter(product=p, order__created_at__gte=day30).aggregate(t=Sum('quantity'))['t'] or 0
        if p.wish_count > sales_30d * 3:
            add(
                'wishlist_demand', 'info',
                f'High Wishlist Demand: {p.name}',
                f"{p.wish_count} customers have {p.name} on their wishlist, "
                f"but only {sales_30d} units were sold in the last 30 days. "
                f"Consider a targeted promotion.",
                metric=f"{p.wish_count} wishlists",
                actions=[
                    {'label': 'View Product', 'href': f'/admin/dashboard/products?id={p.id}'},
                    {'label': 'Create Discount', 'href': f'/admin/dashboard/products?discount={p.id}'},
                ],
                data={'product_id': p.id},
            )

    # ── 13. Search with No Results ───────────────────────────────────────────
    search_pages = (
        PageView.objects.filter(created_at__gte=day7, path__icontains='/search')
        .count()
    )
    if search_pages > 0:
        add(
            'search_opportunity', 'info',
            'Search Activity This Week',
            f"{search_pages} search sessions recorded this week. "
            f"Review top search terms to identify missing products or content gaps.",
            metric=f"{search_pages} searches",
            actions=[
                {'label': 'View Analytics', 'href': '/admin/dashboard/analytics'},
            ],
        )

    # ── 14. Anomaly: Today's orders vs 7-day avg ─────────────────────────────
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.objects.filter(created_at__gte=today_start).count()
    avg_daily = Order.objects.filter(created_at__gte=day7).count() / 7
    if avg_daily > 0:
        ratio = today_orders / avg_daily
        if ratio < 0.4:
            add(
                'anomaly_low', 'warning',
                'Low Order Volume Today',
                f"Today's order count ({today_orders}) is {round((1-ratio)*100)}% below the 7-day daily average ({avg_daily:.0f} orders/day).",
                metric=f"{today_orders} orders today",
                actions=[
                    {'label': 'View Orders', 'href': '/admin/dashboard/orders'},
                ],
            )
        elif ratio > 2.5:
            add(
                'anomaly_high', 'positive',
                'Order Volume Spike Today',
                f"Today's order count ({today_orders}) is {round((ratio-1)*100)}% above the 7-day daily average ({avg_daily:.0f} orders/day).",
                metric=f"{today_orders} orders today",
                actions=[
                    {'label': 'View Orders', 'href': '/admin/dashboard/orders'},
                ],
            )

    # ── 15. Return Rate Spike ────────────────────────────────────────────────
    from orders.models import ReturnRequest
    returns_30d = ReturnRequest.objects.filter(created_at__gte=day30).count()
    returns_prev = ReturnRequest.objects.filter(created_at__gte=day60, created_at__lt=day30).count()
    chg = _pct_change(returns_30d, returns_prev)
    if chg and chg >= 20 and returns_30d >= 3:
        add(
            'return_spike', 'warning',
            'Return Rate Increasing',
            f"Return requests increased {chg:.0f}% this month ({returns_prev} → {returns_30d}). "
            f"Review product quality and descriptions.",
            metric=f"+{chg:.0f}% returns",
            actions=[
                {'label': 'View Returns', 'href': '/admin/dashboard/returns'},
            ],
        )

    # ── 16. Peak Shopping Time ───────────────────────────────────────────────
    from django.db.models.functions import ExtractHour
    peak = (
        Order.objects.filter(created_at__gte=day30)
        .annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('-count')
        .first()
    )
    if peak:
        h = peak['hour']
        label = f"{h}:00–{h+1}:00"
        add(
            'peak_time', 'info',
            'Peak Shopping Time',
            f"Most orders in the last 30 days occur around {label} (UTC). "
            f"Consider scheduling promotions and notifications during this window.",
            metric=f"Peak at {label}",
            actions=[
                {'label': 'View Analytics', 'href': '/admin/dashboard/analytics'},
            ],
        )

    # Sort: critical first, then warning, info, positive
    order_map = {'critical': 0, 'warning': 1, 'info': 2, 'positive': 3}
    insights.sort(key=lambda x: order_map.get(x['severity'], 9))

    return insights
