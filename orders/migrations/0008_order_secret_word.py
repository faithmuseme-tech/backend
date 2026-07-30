from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_returnrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='secret_word',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
