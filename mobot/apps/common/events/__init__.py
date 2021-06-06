from typing import Protocol, NewType
from mobot.apps.common.models import BaseMCModel
from django.db import models
from django.db.models import fields
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.signals import Signal as EventSignal # avoid confusion with Signal client
import datetime



class Event(BaseMCModel):
    class EventType(models.IntegerChoices):
        PAYMENT_STATE_CHANGE_EVENT = 1

    event_type = models.IntegerField(choices=EventType.choices)
    event_body = JSONField(blank=False)
    created_at = models.DateTimeField(default=datetime.datetime.utcnow())

    @staticmethod
    def make_event(event_type: EventType, event_body: str):
        event = Event(event_type, event_body)
        event.save()




