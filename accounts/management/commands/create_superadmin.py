from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

ADMIN_EMAIL = 'primeaisle@admin.com'
ADMIN_PASSWORD = 'primeaisle@admin2026'
ADMIN_USERNAME = 'PrimeAisle'


class Command(BaseCommand):
    help = 'Create or update superadmin'

    def handle(self, *args, **kwargs):
        user, created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={'username': ADMIN_USERNAME},
        )
        user.username = ADMIN_USERNAME
        user.is_staff = True
        user.is_superuser = True
        user.is_admin = True
        user.is_active = True
        user.set_password(ADMIN_PASSWORD)
        user.save()

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Superadmin {ADMIN_EMAIL} {action} successfully.'))
