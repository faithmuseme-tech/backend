from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.text import slugify
from django.core.cache import cache
from .models import Category
from .serializers import CategorySerializer
from adminpanel.permissions import IsAdminUser


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('name')

    def list(self, request, *args, **kwargs):
        data = cache.get('category_list')
        if data is None:
            response = super().list(request, *args, **kwargs)
            cache.set('category_list', response.data, 600)  # 10 minutes
            return response
        from rest_framework.response import Response
        return Response(data)


class CategoryDetailView(generics.RetrieveAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().order_by('name')

    def perform_create(self, serializer):
        name = self.request.data.get('name', '')
        slug = slugify(name)
        base, counter = slug, 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        serializer.save(slug=slug)
        cache.delete('category_list')


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

    def perform_update(self, serializer):
        name = self.request.data.get('name', serializer.instance.name)
        slug = slugify(name)
        base, counter = slug, 1
        while Category.objects.filter(slug=slug).exclude(pk=serializer.instance.pk).exists():
            slug = f"{base}-{counter}"
            counter += 1
        serializer.save(slug=slug)
        cache.delete('category_list')

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete('category_list')
