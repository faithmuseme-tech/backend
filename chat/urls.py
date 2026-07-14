from django.urls import path
from .views import (
    MyRoomView, MyRoomUnreadView,
    AdminRoomListView, AdminRoomDetailView, AdminUnreadTotalView,
)

urlpatterns = [
    # User endpoints
    path('my/',            MyRoomView.as_view(),        name='my_chat_room'),
    path('my/unread/',     MyRoomUnreadView.as_view(),  name='my_chat_unread'),
    # Admin endpoints
    path('admin/rooms/',              AdminRoomListView.as_view(),   name='admin_chat_rooms'),
    path('admin/rooms/<int:room_id>/', AdminRoomDetailView.as_view(), name='admin_chat_room'),
    path('admin/unread/',             AdminUnreadTotalView.as_view(), name='admin_chat_unread'),
]
