import uuid
from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Avg, Count, OuterRef, Subquery
from django.utils.text import slugify
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from .models import Product, ProductImage
from .serializers import ProductSerializer, ProductListSerializer, ProductImageSerializer


def is_approved_trader(user):
    return (
        user.is_authenticated and
        user.is_trader and
        hasattr(user, 'trader_profile') and
        user.trader_profile.is_approved
    )


def annotated_product_qs():
    """Base queryset with avg_rating and review_count annotated in SQL — eliminates N+1."""
    return (
        Product.objects
        .filter(is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('images')
        .annotate(
            _avg_rating=Avg('reviews__rating'),
            _review_count=Count('reviews'),
        )
    )


# Cache 5 min for public unauthenticated list views
CACHE_5M  = 60 * 5
CACHE_10M = 60 * 10


def clear_product_caches():
    """Clear all product list caches so deletions appear immediately."""
    from django.core.cache import cache
    cache.clear()


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'brand__name', 'category__name']
    ordering_fields = ['price', 'created_at', 'avg_rating']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = annotated_product_qs()
        category  = self.request.query_params.get('category')
        brand     = self.request.query_params.get('brand')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        in_stock  = self.request.query_params.get('in_stock')

        if category:  qs = qs.filter(category__slug=category)
        if brand:     qs = qs.filter(brand__slug=brand)
        if min_price: qs = qs.filter(price__gte=min_price)
        if max_price: qs = qs.filter(price__lte=max_price)
        if in_stock == 'true': qs = qs.filter(stock__gt=0)
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        return (
            Product.objects
            .filter(is_active=True)
            .select_related('brand', 'category')
            .prefetch_related('images', 'reviews__user')
            .annotate(_avg_rating=Avg('reviews__rating'), _review_count=Count('reviews'))
        )

    def get_object(self):
        lookup = self.kwargs.get('slug')
        qs = self.get_queryset()
        if str(lookup).isdigit():
            return generics.get_object_or_404(qs, pk=lookup)
        return generics.get_object_or_404(qs, slug=lookup)


@method_decorator(cache_page(CACHE_10M), name='list')
class FeaturedProductsView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return annotated_product_qs().filter(is_featured=True)[:12]


@method_decorator(cache_page(CACHE_10M), name='list')
class NewArrivalsView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return annotated_product_qs().filter(is_new_arrival=True)[:12]


@method_decorator(cache_page(CACHE_10M), name='list')
class BestSellersView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        result = list(annotated_product_qs().filter(is_best_seller=True).order_by('-_review_count', '-_avg_rating'))
        if len(result) < 8:
            existing_ids = {p.id for p in result}
            result += list(
                annotated_product_qs()
                .exclude(id__in=existing_ids)
                .order_by('-_review_count', '-_avg_rating')[:8 - len(result)]
            )
        return result


@method_decorator(cache_page(CACHE_5M), name='list')
class FlashDealsView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return annotated_product_qs().filter(original_price__isnull=False).order_by('-created_at')[:8]


class SearchView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        q = self.request.query_params.get('q', '').strip()
        if not q:
            return Product.objects.none()

        base_qs = annotated_product_qs()
        tokens = [t for t in q.split() if t]
        combined = Q()
        for token in tokens:
            combined |= (
                Q(name__icontains=token) |
                Q(description__icontains=token) |
                Q(brand__name__icontains=token) |
                Q(category__name__icontains=token) |
                Q(badge__icontains=token) |
                Q(sku__icontains=token)
            )
        combined |= (
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(brand__name__icontains=q) |
            Q(category__name__icontains=q)
        )

        direct_hits = base_qs.filter(combined)
        hit_category_ids = direct_hits.values_list('category_id', flat=True).distinct()
        category_related = base_qs.filter(category_id__in=hit_category_ids).exclude(
            id__in=direct_hits.values_list('id', flat=True)
        )

        from itertools import chain
        return list(chain(direct_hits, category_related))


@method_decorator(cache_page(CACHE_5M), name='list')
class RelatedProductsView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        slug = self.kwargs["slug"]
        try:
            product = Product.objects.get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Product.objects.none()

        qs = annotated_product_qs().exclude(slug=slug)
        same_category = list(qs.filter(category=product.category)[:4])
        if len(same_category) >= 4:
            return same_category
        same_brand = list(
            qs.filter(brand=product.brand).exclude(category=product.category)[:4 - len(same_category)]
        )
        return same_category + same_brand




# ── Behavior Tracking & Recommendations ──────────────────────────────────────

class TrackBehaviorView(APIView):
    """POST {product_slug, seconds_spent} — stores a view event keyed by session/user."""
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        from .models import UserBehavior
        slug = request.data.get('product_slug')
        seconds = int(request.data.get('seconds_spent', 0))
        if not slug or seconds < 2:
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            product = Product.objects.select_related('category', 'brand').get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Use user id if authenticated, else session key, else IP
        if request.user and request.user.is_authenticated:
            key = f"user_{request.user.id}"
        else:
            key = request.session.session_key or request.META.get('REMOTE_ADDR', 'anon')

        UserBehavior.objects.create(
            session_key=key,
            product=product,
            category=product.category,
            brand=product.brand,
            seconds_spent=seconds,
        )
        # Keep only last 200 events per session to avoid unbounded growth
        ids = list(
            UserBehavior.objects.filter(session_key=key)
            .order_by('-created_at')
            .values_list('id', flat=True)[200:]
        )
        if ids:
            UserBehavior.objects.filter(id__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecommendedProductsView(generics.ListAPIView):
    """Returns products personalised to the session/user browsing history."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        from .models import UserBehavior
        from django.db.models import Sum

        request = self.request
        if request.user and request.user.is_authenticated:
            key = f"user_{request.user.id}"
        else:
            key = request.session.session_key or request.META.get('REMOTE_ADDR', 'anon')

        # Aggregate time spent per category and brand from last 50 events
        events = UserBehavior.objects.filter(session_key=key).order_by('-created_at')[:50]

        cat_time = {}
        brand_time = {}
        seen_product_ids = set()
        for e in events:
            seen_product_ids.add(e.product_id)
            if e.category_id:
                cat_time[e.category_id] = cat_time.get(e.category_id, 0) + e.seconds_spent
            if e.brand_id:
                brand_time[e.brand_id] = brand_time.get(e.brand_id, 0) + e.seconds_spent

        if not cat_time and not brand_time:
            # No history — return latest products
            return annotated_product_qs().order_by('-created_at')[:12]

        top_cats = sorted(cat_time, key=cat_time.get, reverse=True)[:3]
        top_brands = sorted(brand_time, key=brand_time.get, reverse=True)[:3]

        qs = annotated_product_qs().exclude(id__in=seen_product_ids)
        results = list(qs.filter(category_id__in=top_cats)[:8])
        brand_ids_seen = {p.brand_id for p in results}
        extra = list(
            qs.filter(brand_id__in=top_brands)
            .exclude(id__in=[p.id for p in results])[:max(0, 12 - len(results))]
        )
        combined = results + extra
        if len(combined) < 8:
            fallback = list(
                annotated_product_qs()
                .exclude(id__in=[p.id for p in combined] + list(seen_product_ids))
                .order_by('-created_at')[:12 - len(combined)]
            )
            combined += fallback
        return combined[:12]


class DiverseNewArrivalsView(generics.ListAPIView):
    """New arrivals guaranteed to mix categories and brands (max 2 per category/brand)."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        qs = annotated_product_qs().filter(is_new_arrival=True).order_by('-created_at')
        seen_cats = {}
        seen_brands = {}
        result = []
        for p in qs[:60]:  # scan up to 60 to fill 12 diverse slots
            cat_id = p.category_id
            brand_id = p.brand_id
            if seen_cats.get(cat_id, 0) >= 2:
                continue
            if seen_brands.get(brand_id, 0) >= 2:
                continue
            result.append(p)
            seen_cats[cat_id] = seen_cats.get(cat_id, 0) + 1
            seen_brands[brand_id] = seen_brands.get(brand_id, 0) + 1
            if len(result) == 12:
                break
        # Pad with latest if not enough diverse new arrivals
        if len(result) < 8:
            existing_ids = {p.id for p in result}
            extras = list(
                annotated_product_qs()
                .exclude(id__in=existing_ids)
                .order_by('-created_at')[:12 - len(result)]
            )
            result += extras
        return result


# \u2500\u2500 Trader Product Views \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

class ProductShareView(APIView):
    """Returns an HTML page with OG meta tags for social sharing, then redirects to the frontend."""
    permission_classes = []
    authentication_classes = []

    def get(self, request, slug):
        from django.http import HttpResponse
        FRONTEND = 'https://faithmuseme-tech.github.io/frontend'
        try:
            product = (
                Product.objects
                .filter(slug=slug, is_active=True)
                .prefetch_related('images')
                .select_related('brand', 'category')
                .get()
            )
        except Product.DoesNotExist:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(FRONTEND)

        img = product.images.filter(is_primary=True).first() or product.images.first()
        img_url = ''
        if img:
            url = img.image.url
            img_url = url if url.startswith('http') else request.build_absolute_uri(url)

        price = f"UGX {product.price:,.0f}" if product.price else ''
        title = f"{product.name} — {price}"
        desc  = (product.description or f"Buy {product.name} at {price} on CartPulse.")[:200]
        page_url = f"{FRONTEND}/product/{slug}"
        fallback_img = f"{FRONTEND}/logo512.png"
        og_image = img_url or fallback_img

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta property="og:type"        content="product">
  <meta property="og:site_name"   content="CartPulse">
  <meta property="og:title"       content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:image"       content="{og_image}">
  <meta property="og:image:width" content="800">
  <meta property="og:image:height" content="800">
  <meta property="og:url"         content="{page_url}">
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:title"       content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image"       content="{og_image}">
  <meta http-equiv="refresh" content="0;url={page_url}">
  <script>window.location.replace("{page_url}");</script>
</head>
<body>
  <p>Redirecting to <a href="{page_url}">{title}</a>...</p>
</body>
</html>"""
        return HttpResponse(html, content_type='text/html')


class TraderProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'category__name', 'brand__name']
    pagination_class = None  # Return all trader's products unpaginated

    def get_serializer_class(self):
        return ProductSerializer if self.request.method == 'POST' else ProductListSerializer

    def get_queryset(self):
        return (
            Product.objects
            .filter(seller=self.request.user)
            .select_related('brand', 'category')
            .prefetch_related('images')
            .annotate(_avg_rating=Avg('reviews__rating'), _review_count=Count('reviews'))
        )

    def perform_create(self, serializer):
        if not is_approved_trader(self.request.user):
            raise PermissionDenied('Your trader account is not approved yet.')
        uid = str(uuid.uuid4())[:8]
        slug = slugify(self.request.data.get('name', uid)) + '-' + uid
        while Product.objects.filter(slug=slug).exists():
            slug = slugify(self.request.data.get('name', uid)) + '-' + str(uuid.uuid4())[:8]
        serializer.save(seller=self.request.user, slug=slug)


class TraderProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)

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
        clear_product_caches()


class TraderProductImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, seller=request.user)
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
            img = ProductImage.objects.get(id=image_id, product__seller=request.user)
        except ProductImage.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        img.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
