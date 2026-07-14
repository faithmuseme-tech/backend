from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer

User = get_user_model()


def is_admin(user):
    return user.is_staff or getattr(user, 'is_admin', False)


# ── User: get or create own room, send message, fetch messages ────────────────

class MyRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = 'trader' if getattr(request.user, 'is_trader', False) else 'customer'
        room, _ = ChatRoom.objects.get_or_create(user=request.user, defaults={'role': role})
        # Mark admin messages as read when user opens chat
        room.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        messages = room.messages.select_related('sender').all()
        return Response({
            'room_id': room.id,
            'messages': ChatMessageSerializer(messages, many=True).data,
        })

    def post(self, request):
        body = request.data.get('body', '').strip()
        if not body:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        role = 'trader' if getattr(request.user, 'is_trader', False) else 'customer'
        room, _ = ChatRoom.objects.get_or_create(user=request.user, defaults={'role': role})
        msg = ChatMessage.objects.create(room=room, sender=request.user, body=body)
        room.save()  # update updated_at
        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class MyRoomUnreadView(APIView):
    """Lightweight poll endpoint — returns unread count for the user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            room = request.user.chat_room
            count = room.messages.exclude(sender=request.user).filter(is_read=False).count()
        except ChatRoom.DoesNotExist:
            count = 0
        return Response({'count': count})


# ── Admin: list all rooms, open a room, reply ─────────────────────────────────

class AdminRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        rooms = ChatRoom.objects.select_related('user').prefetch_related('messages').all()
        return Response(ChatRoomSerializer(rooms, many=True).data)


class AdminRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        if not is_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # Mark user messages as read when admin opens
        room.messages.filter(sender=room.user, is_read=False).update(is_read=True)
        messages = room.messages.select_related('sender').all()
        return Response({
            'room': ChatRoomSerializer(room).data,
            'messages': ChatMessageSerializer(messages, many=True).data,
        })

    def post(self, request, room_id):
        if not is_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        body = request.data.get('body', '').strip()
        if not body:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        msg = ChatMessage.objects.create(room=room, sender=request.user, body=body)
        room.save()
        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class AdminUnreadTotalView(APIView):
    """Total unread messages across all rooms for admin badge."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        total = ChatMessage.objects.filter(
            room__user__isnull=False,
            is_read=False
        ).exclude(sender__is_staff=True).exclude(sender__is_admin=True).count()
        return Response({'count': total})
