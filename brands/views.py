from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.db.models import Count, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Brand
from .serializers import BrandSerializer

CACHE_10M = 60 * 10


def brand_qs():
    """Annotate product_count in SQL — avoids N+1 per brand."""
    return (
        Brand.objects
        .filter(is_active=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .order_by('name')
    )


@method_decorator(cache_page(CACHE_10M), name='list')
class BrandListView(generics.ListAPIView):
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return brand_qs()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class BrandDetailView(generics.RetrieveAPIView):
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return brand_qs()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}
