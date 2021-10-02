# Copyright (c) 2021 MobileCoin. All rights reserved.
import attr
import logging
import re
import time
from halo import Halo
from typing import Callable, Optional, Any
from concurrent.futures import as_completed, ThreadPoolExecutor, Future
from django.conf import settings

from mobot_client.chat_strings import ChatStrings
from mobot_client.core import ConfigurationException
from mobot_client.logger import SignalMessenger
from mobot_client.models import Store
from mobot_client.models.messages import Message
from mobot_client.core.context import ChatContext


@attr.s
class ChatHandler:
    regex = attr.ib(type=str)
    callable = attr.ib(type=Callable[[ChatContext], Any])
    order = attr.ib(type=Optional[int], default=100)


class Subscriber:
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """

    def __init__(self, store: Store, messenger: SignalMessenger):
        self._run = True
        self._chat_handlers = []
        self._payment_handlers = []
        self.store: Store = store
        if not self.store:
            raise ConfigurationException("No store found!")
        self.logger = logging.getLogger(f"MOBot({self.store})")
        self.messenger = messenger

        self._number_processed = 0
        self._pool = ThreadPoolExecutor(max_workers=4)
        self._futures = {}

    def _isolated_handler(self, func):
        def isolated(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                self.logger.exception(f"Chat exception while processing: --- {func.__name__}({args}, {kwargs})\n")
        return isolated

    def register_chat_handler(self, regex, func, order=100):
        self.logger.info(f"Registering chat handler for {regex if regex else 'default'}")
        regex = re.compile(regex, re.I)

        self._chat_handlers.append((order, regex, self._isolated_handler(func)))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def register_payment_handler(self, func):
        isolated = self._isolated_handler(func)
        self._payment_handlers.append(isolated)
        return isolated

    def _find_handler(self, message: Message) -> Callable:
        """Perform a regex match search to find an appropriate handler for an incoming message"""
        self.logger.info(f"Finding handler for message {message}")
        if message.text is None:
            return self.handle_payment
        else:
            filtered = list(filter(lambda handler: re.search(handler[1], message.text), self._chat_handlers))[0]
            _, _, func = filtered
            return func

    def acknowledge_message(self, message: Message):
        if message.payment is not None:
            self.logger.info("Customer sent payment; acknowledging immediately")
            self.messenger.log_and_send_message(ChatStrings.PAYMENT_RECEIVED)
        if Message.objects.queue_size >= settings.CONCURRENCY_WARNING_MESSAGE_THRESHOLD:
            self.logger.info(f"Queue threshold {Message.objects.queue_size} above {settings.CONCURRENCY_WARNING_MESSAGE_THRESHOLD}")
            self.messenger.log_and_send_message(ChatStrings.MOBOT_HEAVY_LOAD)

    def process_message(self, message: Message) -> Message:
        """Enter a chat context to manage which message/payment we're currently replying to
            :param: message: Message to process

            :return: The processed message
            :rtype: Message
        """
        with ChatContext(message) as ctx:
            try:
                self.acknowledge_message(message)
                self.logger.exception("Got exception acking")
                handler = self._find_handler(message)
                result = handler(ctx)
                return message
            except Exception as e:
                self.logger.exception("Processing message failed!")
                raise e

    @Halo(text='Waiting for next message...', spinner='dots')
    def _get_next_message(self) -> Message:
        """
        Get a message off the DB, show a spinner while waiting

        :return: The next available message to process
        :rtype: Message
        """
        while self._run:
            try:
                message = Message.objects.get_message(self.store)
                if message:
                    return message
                else:
                    time.sleep(1)
            except Exception as e:
                self.logger.exception("Exception getting message!")
                raise e

    def _get_and_process(self, pool: ThreadPoolExecutor) -> Future[Message]:
        try:
            message: Message = self._get_next_message()
            self.logger.info("Got message!")
            process_fut = pool.submit(self.process_message, message)
            self._futures[message.pk] = process_fut
            return process_fut
        except Exception as e:
            self.logger.exception(f"Exception processing messages.")

    def stop_chat(self):
        self._run = False
        try:
            for future in as_completed(self._futures.values()):
                future.result()
        except Exception:
            self.logger.exception("Error stopping chat")

        self.logger.warning("Stopping message processing!")

    def _done(self, fut: Future[Message]):
        """
        Clean up future list
        :param fut: The message future
        :return: None
        """
        try:
            result = fut.result()
            del self._futures[result.pk]
        except TimeoutError as e:
            self.logger.exception("Message processing timed out.")
        except Exception as e:
            self.logger.exception("Error cleaning up future")

    def run_chat(self, process_max: int = 0) -> int:
        """Start looking for messages off DB and process.
                :argument process_max: Number of messages to process before stopping, if > 0
        """
        self.logger.info("Now running MOBot chat...")
        with self._pool as pool:
            while self._run:
                processed = self._get_and_process(pool)
                processed.add_done_callback(self._done)
                self._number_processed += 1
                if process_max > 0 and self._number_processed == process_max:
                    self.stop_chat()
            self.stop_chat()

