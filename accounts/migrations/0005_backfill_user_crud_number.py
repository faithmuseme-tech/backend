from django.db import migrations


def generate_crud_numbers(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.filter(crud_number__isnull=True):
        user.crud_number = user.crud_number or __import__('uuid').uuid4()
        user.save(update_fields=['crud_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_crud_number'),
    ]

    operations = [
        migrations.RunPython(generate_crud_numbers, reverse_code=migrations.RunPython.noop),
    ]
