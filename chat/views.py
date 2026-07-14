from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import get_user_model
import cloudinary.uploader
from .models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer

User = get_user_model()

ALLOWED_MIME_PREFIXES = ('image/', 'video/')
ALLOWED_EXTENSIONS    = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt')
MAX_FILE_MB           = 20


def is_admin(user):
    return user.is_staff or getattr(user, 'is_admin', False)


def _upload_to_cloudinary(file):
    """Upload file to Cloudinary and return (url, file_type, file_name)."""
    name = file.name.lower()
    mime = getattr(file, 'content_type', '')

    if file.size > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f'File exceeds {MAX_FILE_MB} MB limit.')

    if mime.startswith('image/'):
        resource_type, ftype = 'image', 'image'
    elif mime.startswith('video/'):
        resource_type, ftype = 'video', 'video'
    elif any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        resource_type, ftype = 'raw', 'doc'
    else:
        raise ValueError('Unsupported file type.')

    result = cloudinary.uploader.upload(
        file,
        folder='chat_attachments',
        resource_type=resource_type,
        use_filename=True,
        unique_filename=True,
    )
    return result['secure_url'], ftype, file.name


# ── User: get or create own room, send message, fetch messages ────────────────

class MyRoomView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

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
        file = request.FILES.get('file')
        if not body and not file:
            return Response({'error': 'Message or file required.'}, status=status.HTTP_400_BAD_REQUEST)

        file_url = file_type = file_name = ''
        if file:
            try:
                file_url, file_type, file_name = _upload_to_cloudinary(file)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        reply_to_id = request.data.get('reply_to')
        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = ChatMessage.objects.get(id=reply_to_id)
            except ChatMessage.DoesNotExist:
                pass

        role = 'trader' if getattr(request.user, 'is_trader', False) else 'customer'
        room, _ = ChatRoom.objects.get_or_create(user=request.user, defaults={'role': role})
        msg = ChatMessage.objects.create(
            room=room, sender=request.user,
            body=body, file_url=file_url, file_type=file_type, file_name=file_name,
            reply_to=reply_to_msg,
        )
        room.save()
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
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

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
        file = request.FILES.get('file')
        if not body and not file:
            return Response({'error': 'Message or file required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        file_url = file_type = file_name = ''
        if file:
            try:
                file_url, file_type, file_name = _upload_to_cloudinary(file)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        reply_to_id = request.data.get('reply_to')
        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = ChatMessage.objects.get(id=reply_to_id)
            except ChatMessage.DoesNotExist:
                pass

        msg = ChatMessage.objects.create(
            room=room, sender=request.user,
            body=body, file_url=file_url, file_type=file_type, file_name=file_name,
            reply_to=reply_to_msg,
        )
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
