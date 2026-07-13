from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.text import slugify
from .models import Category
from .serializers import CategorySerializer
from adminpanel.permissions import IsAdminUser


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True).order_by('name')
    serializer_class = CategorySerializer


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
        # ensure uniqueness
        base, counter = slug, 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        serializer.save(slug=slug)


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
