from rest_framework import generics
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Brand
from .serializers import BrandSerializer


class BrandListView(generics.ListAPIView):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer


class BrandDetailView(generics.RetrieveAPIView):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    lookup_field = 'slug'
