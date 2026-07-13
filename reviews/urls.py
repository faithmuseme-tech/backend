from django.urls import path
from .views import ReviewListCreateView, RecentReviewsView

urlpatterns = [
    path('recent/', RecentReviewsView.as_view(), name='recent_reviews'),
    path('<int:product_id>/', ReviewListCreateView.as_view(), name='product_reviews'),
]
