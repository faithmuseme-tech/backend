from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import flashdeals.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0005_product_specs'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FlashDeal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deal_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stock_count', models.PositiveIntegerField(default=50)),
                ('sold_count', models.PositiveIntegerField(default=0)),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('ends_at', models.DateTimeField(default=flashdeals.models.one_week_from_now)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flash_deals', to='products.product')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flash_deals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
