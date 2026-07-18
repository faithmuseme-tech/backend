from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


@receiver(post_save, sender=Order)
def notify_on_delivery(sender, instance, created, **kwargs):
    """When an order is marked delivered, create a rate_product notification per item."""
    if created:
        return
    if instance.status != 'delivered':
        return
    if Notification.objects.filter(user=instance.user, order_id=instance.id, type=Notification.TYPE_RATE_PRODUCT).exists():
        return
    for item in instance.items.select_related('product').all():
        product = item.product
        Notification.objects.create(
            user=instance.user,
            type=Notification.TYPE_RATE_PRODUCT,
            title=f'How was {item.product_name}?',
            message=f'Your order has been delivered. Share your experience with {item.product_name}.',
            product=product,
            order_id=instance.id,
        )


@receiver(post_save, sender=User)
def send_welcome_notification(sender, instance, created, **kwargs):
    """Send a welcome notification when a new user registers."""
    if not created:
        return
    Notification.objects.create(
        user=instance,
        type=Notification.TYPE_WELCOME,
        title='Welcome to Elitetechnology! 🎉',
        message=(
            'Hi there! Welcome to Elitetechnology — Uganda\'s trusted marketplace and delivery platform. '
            'Browse genuine products from verified traders, place your order, and pay via Mobile Money to '
            '0794 448 439 (SABIRA SSEMATA). Our team may call you on 0794 448 439 to confirm your order. '
            'Remember: we will NEVER ask for your PIN or password. '
            'Safety word: AISLE VERIFIED. Enjoy shopping!'
        ),
    )
