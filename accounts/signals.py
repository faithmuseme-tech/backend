from django.db.models.signals import post_delete
from django.dispatch import receiver
from config.cloudinary_utils import delete_cloudinary_file
from .models import User, TraderProfile


@receiver(post_delete, sender=User)
def delete_user_avatar(sender, instance, **kwargs):
    if instance.avatar:
        delete_cloudinary_file(instance.avatar.url)


@receiver(post_delete, sender=TraderProfile)
def delete_trader_logo(sender, instance, **kwargs):
    if instance.logo:
        delete_cloudinary_file(instance.logo.url)
