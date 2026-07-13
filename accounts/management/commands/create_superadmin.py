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
            user = User.objects.get(email=email)
            # Ensure flags are set correctly even if user already exists
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.is_admin = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Admin flags updated for {email}.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Admin {email} already exists.'))
            return

        user = User(
            username=username,
            email=email,
            is_admin=True,
            is_staff=True,
            is_superuser=True,
        )
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Superadmin {email} created successfully.'))
