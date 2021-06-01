import time
from collections import defaultdict
from queue import Queue, Empty
from typing import Iterator

from mobot.apps.merchant_services.models import Customer
from mobot.signald_client.main import MessageSubscriber
from mobot.signald_client.types import Message


class PerCustomerQueueSubscriber(MessageSubscriber):
    def __init__(self, name, *args, **kwargs):
        self._queues = defaultdict(default_factory=lambda phone_number: Queue(maxsize=1000))
        super().__init__(name=name, *args, **kwargs)

    def update(self, message: Message) -> None:
        self._queues[message.source].put(message)

    def get_customer_stream(self, customer: Customer) -> Iterator[Message]:
        while True:
            try:
                cust_queue: Queue = self._queues[customer.phone_number]
                yield cust_queue.get_nowait()
            except Empty as e:
                time.sleep(1.0)
