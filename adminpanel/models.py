from django.db import models
import json


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class SiteSettings(models.Model):
    seller_registration_open = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Site Settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


ALL_PAGES = [
    'orders', 'users', 'traders', 'products',
    'analytics', 'returns', 'chat', 'inquiries',
    'categories', 'brands', 'settings', 'insights',
]


class Employee(models.Model):
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='employee_profile'
    )
    added_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='added_employees'
    )
    permissions = models.JSONField(default=list)  # list of page keys
    must_change_password = models.BooleanField(default=True)
    temp_password = models.CharField(max_length=128, blank=True)  # stores plain temp pw (cleared after first login)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Employee: {self.user.phone}'
