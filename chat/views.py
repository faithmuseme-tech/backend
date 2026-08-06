from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import get_user_model
import cloudinary.uploader
from config.cloudinary_utils import delete_chat_file
from .models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from adminpanel.permissions import HasPagePermission

User = get_user_model()

ALLOWED_MIME_PREFIXES = ('image/', 'video/', 'audio/')
ALLOWED_EXTENSIONS    = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt')
MAX_FILE_MB           = 20


def is_full_admin(user):
    return getattr(user, 'is_admin', False)


def _upload_to_cloudinary(file):
    name = file.name.lower()
    mime = getattr(file, 'content_type', '')
    if file.size > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f'File exceeds {MAX_FILE_MB} MB limit.')
    if mime.startswith('image/'):
        resource_type, ftype = 'image', 'image'
    elif mime.startswith('video/'):
        resource_type, ftype = 'video', 'video'
    elif mime.startswith('audio/'):
        resource_type, ftype = 'video', 'audio'  # Cloudinary uses 'video' resource_type for audio
    elif any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        resource_type, ftype = 'raw', 'doc'
    else:
        raise ValueError('Unsupported file type.')
    result = cloudinary.uploader.upload(
        file, folder='chat_attachments',
        resource_type=resource_type, use_filename=True, unique_filename=True,
    )
    return result['secure_url'], ftype, file.name


class MyRoomView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def _is_employee(self, user):
        return user.is_staff and not user.is_admin and hasattr(user, 'employee_profile')

    def get(self, request):
        if self._is_employee(request.user):
            return Response({'error': 'Employees do not have a personal chat room.'}, status=status.HTTP_403_FORBIDDEN)
        role = 'trader' if getattr(request.user, 'is_trader', False) else 'customer'
        room, _ = ChatRoom.objects.get_or_create(user=request.user, defaults={'role': role})
        room.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        messages = room.messages.select_related('sender').all()
        return Response({'room_id': room.id, 'messages': ChatMessageSerializer(messages, many=True).data})

    def post(self, request):
        if self._is_employee(request.user):
            return Response({'error': 'Employees do not have a personal chat room.'}, status=status.HTTP_403_FORBIDDEN)
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
        reply_to_msg = None
        reply_to_id = request.data.get('reply_to')
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


class MessageDetailView(APIView):
    """Edit or delete a single message (owner only)."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, msg_id):
        try:
            msg = ChatMessage.objects.get(id=msg_id, sender=request.user)
        except ChatMessage.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        new_body = request.data.get('body', '').strip()
        if not new_body:
            return Response({'error': 'Body required.'}, status=status.HTTP_400_BAD_REQUEST)
        msg.body = new_body
        msg.is_edited = True
        msg.save(update_fields=['body', 'is_edited'])
        return Response(ChatMessageSerializer(msg).data)

    def delete(self, request, msg_id):
        try:
            msg = ChatMessage.objects.get(id=msg_id, sender=request.user)
        except ChatMessage.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # Delete file from Cloudinary before wiping the URL
        if msg.file_url and msg.file_type:
            delete_chat_file(msg.file_url, msg.file_type)
        msg.body = ''
        msg.file_url = msg.file_type = msg.file_name = ''
        msg.is_deleted = True
        msg.save(update_fields=['body', 'file_url', 'file_type', 'file_name', 'is_deleted'])
        return Response(ChatMessageSerializer(msg).data)


class MessageBulkDeleteView(APIView):
    """Delete multiple messages at once (owner only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'ids required.'}, status=status.HTTP_400_BAD_REQUEST)
        msgs = ChatMessage.objects.filter(id__in=ids, sender=request.user)
        # Delete Cloudinary files before wiping URLs
        for msg in msgs:
            if msg.file_url and msg.file_type:
                delete_chat_file(msg.file_url, msg.file_type)
        msgs.update(body='', file_url='', file_type='', file_name='', is_deleted=True)
        return Response({'deleted': list(msgs.values_list('id', flat=True))})


class MyRoomUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff and not request.user.is_admin:
            return Response({'count': 0})
        try:
            room = request.user.chat_room
            count = room.messages.exclude(sender=request.user).filter(is_read=False).count()
        except ChatRoom.DoesNotExist:
            count = 0
        return Response({'count': count})


class AdminRoomListView(APIView):
    permission_classes = [HasPagePermission('chat')]

    def get(self, request):
        qs = ChatRoom.objects.select_related('user', 'assigned_to').prefetch_related('messages')
        if not is_full_admin(request.user):
            # Employees only see rooms assigned to them
            qs = qs.filter(assigned_to=request.user)
        return Response(ChatRoomSerializer(qs.all(), many=True).data)


class AdminRoomDetailView(APIView):
    permission_classes = [HasPagePermission('chat')]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def _get_room(self, request, room_id):
        """Return room if accessible, else None."""
        try:
            room = ChatRoom.objects.select_related('user', 'assigned_to').get(id=room_id)
        except ChatRoom.DoesNotExist:
            return None, Response(status=status.HTTP_404_NOT_FOUND)
        if not is_full_admin(request.user) and room.assigned_to_id != request.user.id:
            return None, Response(status=status.HTTP_403_FORBIDDEN)
        return room, None

    def get(self, request, room_id):
        room, err = self._get_room(request, room_id)
        if err:
            return err
        room.messages.filter(sender=room.user, is_read=False).update(is_read=True)
        messages = room.messages.select_related('sender').all()
        return Response({'room': ChatRoomSerializer(room).data, 'messages': ChatMessageSerializer(messages, many=True).data})

    def post(self, request, room_id):
        room, err = self._get_room(request, room_id)
        if err:
            return err
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
        reply_to_msg = None
        reply_to_id = request.data.get('reply_to')
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


class AdminRoomTransferView(APIView):
    """Transfer a chat room to another admin/employee. Full admin only."""
    permission_classes = [HasPagePermission('chat')]

    def post(self, request, room_id):
        if not is_full_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            room = ChatRoom.objects.select_related('assigned_to').get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        assignee_id = request.data.get('assigned_to')  # null = unassign back to admin pool
        note = request.data.get('note', '').strip()

        if assignee_id is None:
            room.assigned_to = None
        else:
            try:
                assignee = User.objects.get(id=assignee_id, is_staff=True)
            except User.DoesNotExist:
                return Response({'error': 'Assignee not found or not a staff member.'}, status=status.HTTP_400_BAD_REQUEST)
            room.assigned_to = assignee

        room.save(update_fields=['assigned_to'])

        # Post a system message so the customer sees the handoff note
        if note:
            ChatMessage.objects.create(
                room=room, sender=request.user,
                body=f"🔁 Transferred: {note}",
            )
            room.save()  # bump updated_at

        return Response(ChatRoomSerializer(room).data)


class AdminUnreadTotalView(APIView):
    permission_classes = [HasPagePermission('chat')]

    def get(self, request):
        if not is_full_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        total = ChatMessage.objects.filter(
            room__user__isnull=False, is_read=False
        ).exclude(sender__is_staff=True).exclude(sender__is_admin=True).count()
        return Response({'count': total})


class ChatAssigneesView(APIView):
    """List all staff members (admins + chat-permitted employees) for the transfer dropdown."""
    permission_classes = [HasPagePermission('chat')]

    def get(self, request):
        if not is_full_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        staff = User.objects.filter(is_staff=True).select_related('employee_profile')
        data = []
        for u in staff:
            if u.is_admin:
                label = 'Admin'
            else:
                try:
                    perms = u.employee_profile.permissions
                    if 'chat' not in perms:
                        continue
                    label = 'Employee'
                except Exception:
                    continue
            data.append({
                'id': u.id,
                'name': u.first_name or u.email or u.phone,
                'label': label,
            })
        return Response(data)
