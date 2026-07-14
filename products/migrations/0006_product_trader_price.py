from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_specs'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='trader_price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='Price set by trader (before 10% platform commission)'
            ),
        ),
    ]
