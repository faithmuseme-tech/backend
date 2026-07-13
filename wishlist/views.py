from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Wishlist
from .serializers import WishlistSerializer
from products.models import Product


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_wishlist(self, user):
        wishlist, _ = Wishlist.objects.get_or_create(user=user)
        return wishlist

    def get(self, request):
        return Response(WishlistSerializer(self._get_wishlist(request.user)).data)

    def post(self, request):
        """Toggle product in wishlist."""
        product_id = request.data.get('product_id')
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        wishlist = self._get_wishlist(request.user)
        if product in wishlist.products.all():
            wishlist.products.remove(product)
            action = 'removed'
        else:
            wishlist.products.add(product)
            action = 'added'
        return Response({'action': action, **WishlistSerializer(wishlist).data})
