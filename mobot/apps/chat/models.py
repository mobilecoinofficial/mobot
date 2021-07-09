from django.db import models

from mobot.apps.merchant_services.models import Customer, Store


class MessageDirection(models.IntegerChoices):
    MESSAGE_DIRECTION_RECEIVED = 0
    MESSAGE_DIRECTION_SENT = 1

class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)