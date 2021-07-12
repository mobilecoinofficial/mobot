from datetime import datetime

from django.db import models
from django_fsm import FSMIntegerField


from mobot.apps.merchant_services.models import Customer, Store, Trackable, DropSession, Campaign


class MobotBot(Trackable):
    name = models.CharField(blank=False, null=False)
    slug = models.SlugField(primary_key=True)
    campaign = models.OneToOneField(Campaign, db_index=True, on_delete=models.CASCADE, related_name="mobot")


class MobotChatSession(Trackable):
    class State(models.IntegerChoices):
        HELLO = -1, 'greeted'
        ACCEPTED = 0, 'accepted'
    slug = models.SlugField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name="chats", db_index=True)
    customer_initiated = models.BooleanField(help_text="True if the customer initiated the conversation", db_index=True)


class MessageDirection(models.IntegerChoices):
    MESSAGE_DIRECTION_RECEIVED = 0
    MESSAGE_DIRECTION_SENT = 1


class Message(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE, db_index=True)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)
    drop_session = models.ForeignKey(DropSession, on_delete=models.SET_NULL, blank=True, null=True, related_name="messages", db_index=True)
    chat_session = models.ForeignKey(MobotChatSession, on_delete=models.CASCADE, blank=False, null=False, related_name="messages", db_index=True)
