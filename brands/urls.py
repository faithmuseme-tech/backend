from django.urls import path
from .views import BrandListView, BrandDetailView

urlpatterns = [
    path('', BrandListView.as_view(), name='brand_list'),
    path('<slug:slug>/', BrandDetailView.as_view(), name='brand_detail'),
]
