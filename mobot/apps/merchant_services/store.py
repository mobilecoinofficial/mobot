from mobot.apps.mobot_client import models
from typing import Protocol, Any, Optional
from django.conf import settings


class BaseStore(Protocol, models.Store):
    def store_number(self) -> Any: ...
    def store(self) -> Optional[models.Store]: ...


class SignalStore(BaseStore):
    def __init__(self, signal_number):
        self.signal_number = signal_number

    @property
    def store_number(self) -> Any: return self.signal_number


class MobStore(object):
    def __init__(self, store_number=settings.STORE_NUMBER):
        self.store_number = store_number
        self.store = SignalStore.objects.get(phone_number=settings.STORE_NUMBER)