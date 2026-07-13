from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import Notification


@receiver(post_save, sender=Order)
def notify_on_delivery(sender, instance, created, **kwargs):
    """When an order is marked delivered, create a rate_product notification per item."""
    if created:
        return
    if instance.status != 'delivered':
        return

    # Avoid duplicate notifications
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
