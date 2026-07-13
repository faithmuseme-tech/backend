from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Review
from .serializers import ReviewSerializer
from orders.models import Order
from adminpanel.permissions import IsAdminUser


def has_bought_and_received(user, product_id):
    """Check user has a delivered order containing this product."""
    return Order.objects.filter(
        user=user,
        status='delivered',
        items__product_id=product_id,
    ).exists()


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Review.objects.filter(product_id=self.kwargs['product_id'])

    def perform_create(self, serializer):
        product_id = self.kwargs['product_id']
        user = self.request.user

        if not has_bought_and_received(user, product_id):
            raise PermissionDenied('You can only review products from delivered orders.')

        if Review.objects.filter(user=user, product_id=product_id).exists():
            raise ValidationError('You have already reviewed this product.')

        serializer.save(user=user, product_id=product_id)


class ReviewDeleteView(APIView):
    """Only the review owner or a site admin can delete a review. Traders cannot."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            review = Review.objects.get(pk=pk)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Block traders who are not admins
        if request.user.is_trader and not (request.user.is_admin or request.user.is_staff):
            raise PermissionDenied('Traders cannot delete reviews.')

        # Allow only the review owner or a site admin
        is_owner = review.user == request.user
        is_admin = request.user.is_admin or request.user.is_staff

        if not (is_owner or is_admin):
            raise PermissionDenied('You do not have permission to delete this review.')

        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CanReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        already_reviewed = Review.objects.filter(
            user=request.user, product_id=product_id
        ).exists()
        can_review = has_bought_and_received(request.user, product_id)
        return Response({
            'can_review': can_review and not already_reviewed,
            'already_reviewed': already_reviewed,
            'reason': (
                'already_reviewed' if already_reviewed
                else 'not_delivered' if not can_review
                else None
            ),
        })


class RecentReviewsView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        limit = int(self.request.query_params.get('limit', 8))
        return Review.objects.select_related('user', 'product').filter(rating__gte=4).order_by('-created_at')[:limit]
