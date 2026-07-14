from django.db import models
from django.conf import settings


class ChatRoom(models.Model):
    """
    A conversation thread between a user (customer or trader) and admin.
    """
    ROLE_CUSTOMER = 'customer'
    ROLE_TRADER   = 'trader'
    ROLE_CHOICES  = [(ROLE_CUSTOMER, 'Customer'), (ROLE_TRADER, 'Trader')]

    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_room')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.email} ({self.role})"

    @property
    def unread_by_admin(self):
        return self.messages.filter(sender=self.user, is_read=False).count()

    @property
    def unread_by_user(self):
        return self.messages.exclude(sender=self.user).filter(is_read=False).count()


class ChatMessage(models.Model):
    room       = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    body       = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.email}: {self.body[:40]}"
