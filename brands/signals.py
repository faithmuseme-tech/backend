from django.db.models.signals import post_delete
from django.dispatch import receiver
from config.cloudinary_utils import delete_cloudinary_file
from .models import Brand


@receiver(post_delete, sender=Brand)
def delete_brand_logo(sender, instance, **kwargs):
    if instance.logo:
        delete_cloudinary_file(instance.logo.url)
