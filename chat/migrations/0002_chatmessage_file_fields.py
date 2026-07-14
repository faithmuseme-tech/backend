from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatmessage',
            name='body',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='file_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='file_type',
            field=models.CharField(
                blank=True, default='',
                choices=[('image', 'Image'), ('video', 'Video'), ('doc', 'Document')],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='file_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
