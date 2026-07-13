from django.urls import path
from .views import NotificationListView, NotificationMarkReadView, UnreadCountView

urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications'),
    path('unread-count/', UnreadCountView.as_view(), name='unread_count'),
    path('mark-read/', NotificationMarkReadView.as_view(), name='mark_all_read'),
    path('mark-read/<int:pk>/', NotificationMarkReadView.as_view(), name='mark_read'),
]
