from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_userbehavior'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(db_index=True, max_length=64)),
                ('path', models.CharField(db_index=True, max_length=255)),
                ('seconds_spent', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
