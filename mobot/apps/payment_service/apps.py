from django.apps import AppConfig

class PaymentServiceAppConfig(AppConfig):
    name = 'mobot.apps.payment_service'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Payment Service models and service'