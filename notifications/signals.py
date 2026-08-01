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
        title='Welcome to CartPulse! 🎉',
        message=(
            'Hi {name}! Welcome to CartPulse — Uganda\'s trusted online marketplace and doorstep delivery platform.\n\n'
            'We sell genuine electronics, STEM products, industrial equipment, and everyday essentials, '
            'delivered straight to your door across Uganda.\n\n'
            '🛒 HOW TO ORDER\n'
            'Browse products on the CartPulse platform, add items to your cart, and place your order. '
            'Once you submit your order, our team will review it and may call you to confirm.\n\n'
            '💳 HOW TO PAY\n'
            'CartPulse uses Mobile Money only. Send your payment to:\n'
            '  • Number: 0794 448 439\n'
            '  • Name: SABIRA SSEMATA\n'
            'Always confirm the name before sending. Put your full name as the reference so we can match your payment.\n\n'
            '🚚 DELIVERY\n'
            'We deliver directly to your doorstep — you do not need to come and collect. '
            'Delivery is available to selected towns across Uganda. '
            'If you are outside a listed town, contact us first so we can confirm availability and extra charges.\n\n'
            '🔒 STAY SAFE — FRAUD WARNING\n'
            'CartPulse will NEVER ask for your Mobile Money PIN, OTP, or account password. '
            'We will NEVER ask you to send money to any number other than 0794 448 439 (SABIRA SSEMATA). '
            'If anyone claiming to be CartPulse asks for your PIN or asks you to pay a different number — hang up immediately. It is a scam.\n\n'
            'To verify you are speaking with a real CartPulse agent, ask them to confirm your order number — a genuine agent will always know it.\n\n'
            '📞 CONTACT US\n'
            '  • Phone / WhatsApp: 0794 448 439 or 0786 023 858\n'
            '  • Email: information.cartpulse@gmail.com\n\n'
            'Thank you for joining CartPulse. Happy shopping!'
        ).format(name=instance.first_name or 'there'),
    )
