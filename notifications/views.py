from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related('product')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
        else:
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        # Invalidate cached unread count
        cache.delete(f'unread_count_{request.user.id}')
        return Response({'status': 'ok'})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        key = f'unread_count_{request.user.id}'
        count = cache.get(key)
        if count is None:
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            cache.set(key, count, 60)  # cache 60 seconds
        return Response({'count': count})
