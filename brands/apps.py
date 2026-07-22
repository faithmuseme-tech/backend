from django.apps import AppConfig


class BrandsConfig(AppConfig):
    name = 'brands'

    def ready(self):
        import brands.signals  # noqa
