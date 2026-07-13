from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_increase_slug_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='specs',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
