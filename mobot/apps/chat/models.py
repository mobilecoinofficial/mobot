from django.utils import timezone as tz
from django.db import models
from django_fsm import FSMIntegerField

from mobot.signald_client.types import Message as SignalMessage
from mobot.apps.merchant_services.models import Customer, Store, Trackable, DropSession, Campaign


class MobotBotManager(models.Manager):
    def create(self, **kwargs):
        store = kwargs.get('store')
        name = kwargs.get('name')
        campaigns = kwargs.get('campaigns')
        if not name:
            if not campaigns:
                campaigns = 'all'
            name = f"{store.name}-mobot"
        mobot = super().create(name=name, store=store)
        return mobot


class MobotBot(Trackable):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(blank=False, null=False, max_length=255, db_index=True, unique=True)
    store = models.ForeignKey(Store, db_index=True, on_delete=models.CASCADE, related_name="mobots")
    campaigns = models.ManyToManyField(Campaign, db_index=True, related_name="mobots")
    objects = MobotBotManager()

    @property
    def single_campaign(self) -> bool:
        len(self.campaigns) == 1


class MobotChatSession(Trackable):
    class State(models.IntegerChoices):
        HELLO = 0, 'greeted'
        ACCEPTED = 1, 'accepted'
    slug = models.SlugField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name="mobot_chat_sessions", db_index=True, blank=False, null=False)
    customer_initiated = models.BooleanField(help_text="True if the customer initiated the conversation", db_index=True, default=False)
    mobot = models.ForeignKey(MobotBot, on_delete=models.DO_NOTHING, related_name="mobot_chat_sessions")
    state = FSMIntegerField(choices=State.choices, default=State.HELLO, protected=True)
    drop_session = models.OneToOneField(DropSession, related_name="chat", on_delete=models.CASCADE)

    class Meta:
        unique_together = ['mobot', 'customer']


class MessageDirection(models.IntegerChoices):
    MESSAGE_DIRECTION_RECEIVED = 0
    MESSAGE_DIRECTION_SENT = 1


class Message(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE, db_index=True)
    text = models.TextField()
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)
    chat_session = models.ForeignKey(MobotChatSession, on_delete=models.CASCADE, blank=False, null=False, related_name="messages", db_index=True)
