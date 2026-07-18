from django.contrib import admin
from django.urls import path, include, re_path
import config.admin_register  # noqa: registers all models
from django.conf import settings
from django.conf.urls.static import static
import requests as _requests
from django.http import HttpResponse, Http404


def media_proxy(request, path):
    """Proxy /media/<path> → Cloudinary, hiding the real storage URL."""
    import cloudinary
    cloud = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
    cloudinary_url = f"https://res.cloudinary.com/{cloud}/image/upload/v1/media/{path}"
    try:
        resp = _requests.get(cloudinary_url, timeout=10)
        if resp.status_code != 200:
            raise Http404
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        response = HttpResponse(resp.content, content_type=content_type)
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    except _requests.RequestException:
        raise Http404


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
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/flash-deals/', include('flashdeals.urls')),
    path('api/v1/admin/', include('adminpanel.urls')),
    path('api/v1/chat/', include('chat.urls')),
    re_path(r'^media/(?P<path>.+)$', media_proxy, name='media_proxy'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
