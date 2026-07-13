from django.contrib import admin
from django.urls import path, include
import config.admin_register  # noqa: registers all models
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/brands/', include('brands.urls')),
    path('api/v1/categories/', include('categories.urls')),
    path('api/v1/products/', include('products.urls')),
    path('api/v1/reviews/', include('reviews.urls')),
    path('api/v1/cart/', include('cart.urls')),
    path('api/v1/wishlist/', include('wishlist.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/admin/', include('adminpanel.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
