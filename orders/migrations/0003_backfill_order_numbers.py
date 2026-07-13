from django.db import migrations


def generate_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    User = apps.get_model('accounts', 'User')
    for order in Order.objects.filter(user_crud_number__isnull=True):
        order.order_number = order.order_number or __import__('uuid').uuid4()
        if order.user_id:
            try:
                user = User.objects.get(pk=order.user_id)
                order.user_crud_number = user.crud_number
            except User.DoesNotExist:
                order.user_crud_number = __import__('uuid').uuid4()
        else:
            order.user_crud_number = __import__('uuid').uuid4()
        order.save(update_fields=['order_number', 'user_crud_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_order_number_order_user_crud_number'),
        ('accounts', '0005_backfill_user_crud_number'),
    ]

    operations = [
        migrations.RunPython(generate_order_numbers, reverse_code=migrations.RunPython.noop),
    ]
