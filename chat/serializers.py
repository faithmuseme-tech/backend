from rest_framework import serializers
from .models import ChatRoom, ChatMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class ReplySnippetSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model  = ChatMessage
        fields = ('id', 'body', 'file_type', 'file_name', 'sender_name')

    def get_sender_name(self, obj):
        return obj.sender.first_name or obj.sender.email.split('@')[0]


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name  = serializers.SerializerMethodField()
    is_admin_msg = serializers.SerializerMethodField()
    reply_to     = ReplySnippetSerializer(read_only=True)

    class Meta:
        model  = ChatMessage
        fields = ('id', 'body', 'file_url', 'file_type', 'file_name',
                  'sender', 'sender_name', 'is_admin_msg', 'is_read',
                  'is_edited', 'is_deleted', 'reply_to', 'created_at')

    def get_sender_name(self, obj):
        return obj.sender.first_name or obj.sender.email.split('@')[0]

    def get_is_admin_msg(self, obj):
        return obj.sender.is_staff or obj.sender.is_admin


class ChatRoomSerializer(serializers.ModelSerializer):
    user_email      = serializers.CharField(source='user.email', read_only=True)
    user_name       = serializers.SerializerMethodField()
    last_message    = serializers.SerializerMethodField()
    unread_by_admin = serializers.IntegerField(read_only=True)
    unread_by_user  = serializers.IntegerField(read_only=True)

    class Meta:
        model  = ChatRoom
        fields = ('id', 'user', 'user_email', 'user_name', 'role',
                  'unread_by_admin', 'unread_by_user', 'last_message', 'updated_at')

    def get_user_name(self, obj):
        return obj.user.first_name or obj.user.email.split('@')[0]

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if not msg:
            return None
        return {'body': msg.body[:60], 'created_at': msg.created_at}
