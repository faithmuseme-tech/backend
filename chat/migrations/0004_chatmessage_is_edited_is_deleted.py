from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_chatmessage_reply_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='is_edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
