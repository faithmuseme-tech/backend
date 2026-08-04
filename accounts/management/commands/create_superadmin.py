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
        phone = config('ADMIN_PHONE', default='')

        if not email or not password:
            self.stdout.write(self.style.WARNING('ADMIN_EMAIL or ADMIN_PASSWORD not set, skipping.'))
            return

        # Also try to find by phone in case email changed
        user = None
        if phone:
            user = User.objects.filter(phone=phone).first()
        if user is None:
            user = User.objects.filter(email=email).first()

        created = False
        if user is None:
            user = User(email=email, username=username, phone=phone)
            created = True
        else:
            user.username = username
            if phone:
                user.phone = phone
            if email:
                user.email = email

        user.is_staff = True
        user.is_superuser = True
        user.is_admin = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Superadmin {email} {action} successfully.'))
