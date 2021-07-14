from django.db import models
from django_fsm import FSMIntegerField

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
    name = models.CharField(blank=False, null=False, max_length=255, db_index=True, unique=True)
    store = models.ForeignKey(Store, db_index=True, on_delete=models.CASCADE, related_name="mobots")
    campaign = models.OneToOneField(Campaign, db_index=True, related_name="mobot", on_delete=models.DO_NOTHING)
    objects = MobotBotManager()

    @property
    def single_campaign(self) -> bool:
        len(self.campaigns) == 1


class MobotChatSession(Trackable):
    class State(models.IntegerChoices):
        NOT_GREETED = 0, 'not_greeted'
        INTRODUCTION_GIVEN = 1, 'introduction_given'
    slug = models.SlugField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name="mobot_chat_sessions", db_index=True, blank=False, null=False)
    customer_initiated = models.BooleanField(help_text="True if the customer initiated the conversation", db_index=True, default=False)
    mobot = models.ForeignKey(MobotBot, on_delete=models.DO_NOTHING, related_name="mobot_chat_sessions")
    state = FSMIntegerField(choices=State.choices, default=State.NOT_GREETED, protected=True)
    drop_session = models.OneToOneField(DropSession, related_name="chat", on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        unique_together = ['mobot', 'customer']


class MessageDirection(models.IntegerChoices):
    MESSAGE_DIRECTION_RECEIVED = 0, 'received'
    MESSAGE_DIRECTION_SENT = 1, 'sent'


class Message(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True)
    text = models.TextField()
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)
    chat_session = models.ForeignKey(MobotChatSession, on_delete=models.CASCADE, blank=False, null=False, related_name="messages", db_index=True)

    def __str__(self):
        return f"{self.customer.phone_number}-{self.text}-{self.direction}"
