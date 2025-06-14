from django.apps import AppConfig


class EimsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eims'

def ready(self):
    import eims.signals  # noqa: F401

