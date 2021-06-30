from django.apps import AppConfig

class CommonAppConfig(AppConfig):
    name = 'mobot.apps.common'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Merchant common models and events'