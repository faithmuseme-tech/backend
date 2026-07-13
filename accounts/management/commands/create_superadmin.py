from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

User = get_user_model()


class Command(BaseCommand):
    help = 'Create superadmin from environment variables if not exists'

    def handle(self, *args, **kwargs):
        email = config('ADMIN_EMAIL', default='')
        password = config('ADMIN_PASSWORD', default='')
        username = config('ADMIN_USERNAME', default='admin')

        if not email or not password:
            self.stdout.write(self.style.WARNING('ADMIN_EMAIL or ADMIN_PASSWORD not set, skipping.'))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(f'Admin {email} already exists.'))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            is_admin=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Superadmin {email} created successfully.'))
