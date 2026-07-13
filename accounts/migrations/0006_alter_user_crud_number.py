from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_backfill_user_crud_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='crud_number',
            field=models.UUIDField(default=__import__('uuid').uuid4, editable=False, unique=True),
        ),
    ]
