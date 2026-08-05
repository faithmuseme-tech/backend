from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_alter_notification_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(
                choices=[
                    ('rate_product',  'Rate Product'),
                    ('order_update',  'Order Update'),
                    ('welcome',       'Welcome'),
                    ('return_update', 'Return Update'),
                    ('loyalty_points', 'Loyalty Points'),
                ],
                max_length=30,
            ),
        ),
    ]
