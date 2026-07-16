from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q
from django.utils.text import slugify
from django.core.cache import cache
from .models import Brand
from .serializers import BrandSerializer


def is_admin(user):
    return user.is_authenticated and (user.is_admin or user.is_staff)


def brand_qs():
    """Annotate product_count in SQL — avoids N+1 per brand."""
    return (
        Brand.objects
        .filter(is_active=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .order_by('name')
    )


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


# ── Admin Brand CRUD ───────────────────────────────────────────────────────────

class AdminBrandListCreateView(generics.ListCreateAPIView):
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Brand.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def perform_create(self, serializer):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        name = self.request.data.get('name', '')
        slug = slugify(name)
        base, i = slug, 1
        while Brand.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"; i += 1
        serializer.save(slug=slug)
        cache.clear()


class AdminBrandDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Brand.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def perform_update(self, serializer):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        name = self.request.data.get('name', serializer.instance.name)
        if name != serializer.instance.name:
            slug = slugify(name)
            base, i = slug, 1
            while Brand.objects.filter(slug=slug).exclude(pk=serializer.instance.pk).exists():
                slug = f"{base}-{i}"; i += 1
            serializer.save(slug=slug)
        else:
            serializer.save()
        cache.clear()

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        instance.delete()
        cache.clear()
