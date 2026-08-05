from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import LoyaltyAccount, LoyaltyTransaction, PromotionConfig


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
    # Avoid double-awarding if already earned for this order
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


def _reverse_points(order):
    """Reverse any earned points when an order is cancelled or refunded."""
    account = LoyaltyAccount.for_user(order.user)
    earned_tx = LoyaltyTransaction.objects.filter(
        account=account, order_id=order.id, tx_type=LoyaltyTransaction.TYPE_EARN
    ).first()
    if not earned_tx:
        return
    # Avoid double-reversing
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


@receiver(post_save, sender=Order)
def handle_order_status(sender, instance, **kwargs):
    if instance.status == 'delivered':
        _award_points(instance)
    elif instance.status in ('cancelled', 'refunded'):
        _reverse_points(instance)
