from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('brands', '0001_initial'),
        ('categories', '0001_initial'),
        ('products', '0007_product_price_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserBehavior',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(db_index=True, max_length=64)),
                ('seconds_spent', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='brands.brand')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='categories.category')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='behavior_events', to='products.product')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
