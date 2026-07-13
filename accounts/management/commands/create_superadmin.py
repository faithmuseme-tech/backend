from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or update superadmin from environment variables'

    def handle(self, *args, **kwargs):
        email = config('ADMIN_EMAIL', default='')
        password = config('ADMIN_PASSWORD', default='')
        username = config('ADMIN_USERNAME', default='admin')

        if not email or not password:
            self.stdout.write(self.style.WARNING('ADMIN_EMAIL or ADMIN_PASSWORD not set, skipping.'))
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': username},
        )

        user.username = username
        user.is_staff = True
        user.is_superuser = True
        user.is_admin = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Superadmin {email} {action} successfully.'))
