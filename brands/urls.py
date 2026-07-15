from django.urls import path
from .views import BrandListView, BrandDetailView, AdminBrandListCreateView, AdminBrandDetailView

urlpatterns = [
    path('', BrandListView.as_view(), name='brand_list'),
    path('admin/', AdminBrandListCreateView.as_view(), name='admin_brand_list_create'),
    path('admin/<int:pk>/', AdminBrandDetailView.as_view(), name='admin_brand_detail'),
    path('<slug:slug>/', BrandDetailView.as_view(), name='brand_detail'),
]
