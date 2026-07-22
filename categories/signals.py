from django.db.models.signals import post_delete
from django.dispatch import receiver
from config.cloudinary_utils import delete_cloudinary_file
from .models import Category


@receiver(post_delete, sender=Category)
def delete_category_image(sender, instance, **kwargs):
    if instance.image:
        delete_cloudinary_file(instance.image.url)
