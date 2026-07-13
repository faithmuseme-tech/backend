from django.urls import path
from .views import ReviewListCreateView, RecentReviewsView, CanReviewView, ReviewDeleteView

urlpatterns = [
    path('recent/', RecentReviewsView.as_view(), name='recent_reviews'),
    path('can-review/<int:product_id>/', CanReviewView.as_view(), name='can_review'),
    path('<int:product_id>/', ReviewListCreateView.as_view(), name='product_reviews'),
    path('delete/<int:pk>/', ReviewDeleteView.as_view(), name='review_delete'),
]
