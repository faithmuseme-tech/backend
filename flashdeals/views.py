from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import FlashDeal
from .serializers import FlashDealSerializer


def is_approved_trader(user):
    return (
        user.is_authenticated and
        user.is_trader and
        hasattr(user, 'trader_profile') and
        user.trader_profile.is_approved
    )


@method_decorator(cache_page(60 * 2), name='list')   # cache 2 min — countdown needs to be fresh
class FlashDealListView(generics.ListAPIView):
    serializer_class = FlashDealSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        return (
            FlashDeal.objects
            .filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
            .select_related('product__brand', 'product__category')
            .prefetch_related('product__images')
            .order_by('-created_at')
        )


class TraderFlashDealListCreateView(generics.ListCreateAPIView):
    serializer_class = FlashDealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FlashDeal.objects.filter(created_by=self.request.user).select_related('product')

    def perform_create(self, serializer):
        if not is_approved_trader(self.request.user):
            raise PermissionDenied('Your trader account is not approved yet.')
        # ensure the product belongs to this trader
        product = serializer.validated_data.get('product')
        if product.seller != self.request.user:
            raise PermissionDenied('You can only create flash deals for your own products.')
        serializer.save(created_by=self.request.user)


class TraderFlashDealDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            deal = FlashDeal.objects.get(pk=pk, created_by=request.user)
        except FlashDeal.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        deal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
