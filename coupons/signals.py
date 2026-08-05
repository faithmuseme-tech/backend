from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import LoyaltyAccount, LoyaltyTransaction, PromotionConfig
from notifications.models import Notification


def _award_points(order):
    """Award loyalty points for a delivered order based on delivery fee paid."""
    cfg = PromotionConfig.get()
    delivery_fee = int(order.delivery_fee or 0)
    if delivery_fee <= 0:
        return
    units = delivery_fee // cfg.delivery_unit_size
    points = units * cfg.points_per_delivery_unit
    if points <= 0:
        return

    account = LoyaltyAccount.for_user(order.user)
    if LoyaltyTransaction.objects.filter(account=account, order_id=order.id, tx_type=LoyaltyTransaction.TYPE_EARN).exists():
        return

    account.points_balance += points
    account.points_earned  += points
    account.save(update_fields=['points_balance', 'points_earned', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, order_id=order.id,
        tx_type=LoyaltyTransaction.TYPE_EARN, points=points,
        note=f'Earned for delivery fee UGX {delivery_fee:,} on order #{str(order.order_number)[:8].upper()}'
    )

    short_id = str(order.order_number)[:8].upper()
    new_balance = account.points_balance
    pts_label = lambda n: f"{n} point{'s' if n != 1 else ''}"
    Notification.objects.create(
        user=order.user,
        type=Notification.TYPE_LOYALTY,
        title=f'You earned loyalty points!',
        message=(
            f'Your order #{short_id} has been delivered and you\'ve earned {pts_label(points)}.\n\n'
            f'Your current balance is {pts_label(new_balance)}.\n\n'
            f'Keep shopping to earn more rewards. Once you have enough points, '
            f'you can redeem them for a discount on your next order at checkout.\n\n'
            f'Visit your Loyalty Rewards page to track your points and available coupons.'
        ),
        order_id=order.id,
    )


def _reverse_points(order):
    """Reverse any earned points when an order is cancelled or refunded."""
    account = LoyaltyAccount.for_user(order.user)
    earned_tx = LoyaltyTransaction.objects.filter(
        account=account, order_id=order.id, tx_type=LoyaltyTransaction.TYPE_EARN
    ).first()
    if not earned_tx:
        return
    if LoyaltyTransaction.objects.filter(account=account, order_id=order.id, tx_type=LoyaltyTransaction.TYPE_REVERSE).exists():
        return

    account.points_balance = max(0, account.points_balance - earned_tx.points)
    account.points_earned  = max(0, account.points_earned  - earned_tx.points)
    account.save(update_fields=['points_balance', 'points_earned', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, order_id=order.id,
        tx_type=LoyaltyTransaction.TYPE_REVERSE, points=-earned_tx.points,
        note=f'Reversed — order {order.status}'
    )

    short_id = str(order.order_number)[:8].upper()
    pts_label = lambda n: f"{n} point{'s' if n != 1 else ''}"
    Notification.objects.create(
        user=order.user,
        type=Notification.TYPE_LOYALTY,
        title='Loyalty points reversed',
        message=(
            f'The {pts_label(earned_tx.points)} previously earned on order #{short_id} '
            f'have been reversed because the order was {order.status}.\n\n'
            f'Your updated balance is {pts_label(account.points_balance)}.'
        ),
        order_id=order.id,
    )


@receiver(post_save, sender=Order)
def handle_order_status(sender, instance, created, **kwargs):
    if instance.status == 'confirmed' and not created:
        short_id = str(instance.order_number)[:8].upper()
        if not Notification.objects.filter(
            user=instance.user, order_id=instance.id,
            type=Notification.TYPE_ORDER_UPDATE,
            title__startswith='Order confirmed'
        ).exists():
            Notification.objects.create(
                user=instance.user,
                type=Notification.TYPE_ORDER_UPDATE,
                title=f'Order confirmed — #{short_id}',
                message=(
                    f'Your order #{short_id} has been confirmed and is being prepared for dispatch.\n\n'
                    f'Order total: UGX {int(instance.total_price):,}\n'
                    f'Delivery to: {instance.shipping_city}\n\n'
                    f'We will notify you once your order is on its way. '
                    f'You can track your order status anytime from the My Orders page.'
                ),
                order_id=instance.id,
            )
    elif instance.status == 'delivered':
        _award_points(instance)
    elif instance.status in ('cancelled', 'refunded'):
        _reverse_points(instance)
