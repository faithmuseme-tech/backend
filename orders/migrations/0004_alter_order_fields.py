from django.db import migrations, models


def backfill_order_user_crud(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    User = apps.get_model('accounts', 'User')
    for order in Order.objects.filter(user_crud_number__isnull=True):
        if order.user_id:
            try:
                user = User.objects.get(pk=order.user_id)
                order.user_crud_number = user.crud_number
            except User.DoesNotExist:
                order.user_crud_number = __import__('uuid').uuid4()
        else:
            order.user_crud_number = __import__('uuid').uuid4()
        order.save(update_fields=['user_crud_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_backfill_order_numbers'),
    ]

    operations = [
        migrations.RunPython(backfill_order_user_crud, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='order_number',
            field=models.UUIDField(default=__import__('uuid').uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='user_crud_number',
            field=models.UUIDField(editable=False, db_index=True),
        ),
    ]
