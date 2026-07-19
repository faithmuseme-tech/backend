from django.db import models


class SiteSettings(models.Model):
    seller_registration_open = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Site Settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
