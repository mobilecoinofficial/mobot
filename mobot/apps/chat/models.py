from datetime import datetime

from django.db import models
from django_fsm import FSMIntegerField


from mobot.apps.merchant_services.models import Customer, Store, Trackable, DropSession


class MessageDirection(models.IntegerChoices):
    MESSAGE_DIRECTION_RECEIVED = 0
    MESSAGE_DIRECTION_SENT = 1


class Message(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)
    drop_session = models.ForeignKey(DropSession, on_delete=models.CASCADE, blank=False, null=False, related_name="messages")