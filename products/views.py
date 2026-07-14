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
        return annotated_product_qs().filter(is_best_seller=True)[:12]


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


# \u2500\u2500 Trader Product Views \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

class TraderProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
