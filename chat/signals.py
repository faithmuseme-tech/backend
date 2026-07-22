from django.db.models.signals import post_delete
from django.dispatch import receiver
from config.cloudinary_utils import delete_chat_file
from .models import ChatMessage


@receiver(post_delete, sender=ChatMessage)
def delete_chat_message_file(sender, instance, **kwargs):
    if instance.file_url and instance.file_type:
        delete_chat_file(instance.file_url, instance.file_type)
