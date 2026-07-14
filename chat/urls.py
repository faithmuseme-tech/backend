from django.urls import path
from .views import (
    MyRoomView, MyRoomUnreadView,
    AdminRoomListView, AdminRoomDetailView, AdminUnreadTotalView,
    MessageDetailView, MessageBulkDeleteView,
)

urlpatterns = [
    path('my/',                      MyRoomView.as_view(),          name='my_chat_room'),
    path('my/unread/',               MyRoomUnreadView.as_view(),    name='my_chat_unread'),
    path('messages/<int:msg_id>/',   MessageDetailView.as_view(),   name='message_detail'),
    path('messages/bulk-delete/',    MessageBulkDeleteView.as_view(), name='message_bulk_delete'),
    path('admin/rooms/',             AdminRoomListView.as_view(),   name='admin_chat_rooms'),
    path('admin/rooms/<int:room_id>/', AdminRoomDetailView.as_view(), name='admin_chat_room'),
    path('admin/unread/',            AdminUnreadTotalView.as_view(), name='admin_chat_unread'),
]
