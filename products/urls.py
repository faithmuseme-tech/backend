from django.urls import path
from .views import (
    ProductListView, ProductDetailView, FeaturedProductsView,
    NewArrivalsView, BestSellersView, FlashDealsView, SearchView,
    RelatedProductsView, TraderProductListCreateView,
    TraderProductDetailView, TraderProductImageView,
)

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('featured/', FeaturedProductsView.as_view(), name='featured_products'),
    path('new-arrivals/', NewArrivalsView.as_view(), name='new_arrivals'),
    path('best-sellers/', BestSellersView.as_view(), name='best_sellers'),
    path('flash-deals/', FlashDealsView.as_view(), name='flash_deals'),
    path('search/', SearchView.as_view(), name='product_search'),
    # Trader product management
    path('trader/', TraderProductListCreateView.as_view(), name='trader_products'),
    path('trader/<int:pk>/', TraderProductDetailView.as_view(), name='trader_product_detail'),
    path('trader/<int:pk>/images/', TraderProductImageView.as_view(), name='trader_product_images'),
    # Public
    path('<slug:slug>/related/', RelatedProductsView.as_view(), name='related_products'),
    path('<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path('<int:pk>/', ProductDetailView.as_view(), name='product_detail_by_id'),
]
