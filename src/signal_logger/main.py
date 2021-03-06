# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import time

from concurrent.futures import Future
from mobot_client.concurrency import AutoCleanupExecutor

from signald import Signal as _Signal
from signald.types import Message as SignalMessage

from mobot_client.models.messages import Message
from mobot_client.payments import Payments
from mobot_client.payments.client import MCClient



class SignalMessageException(Exception):
    pass


class SignalLogger:
    """A signal logger that logs to our DB instead of running callbacks"""

    def __init__(self, signal: _Signal, payments: Payments, *args, **kwargs):
        self.logger = logging.getLogger("SignalLogger")
        self._payments = payments
        self._signal = signal
        self._run = False

    def _parse_message(self, message: SignalMessage, auto_send_receipts=True) -> Message:
        if not message.text and not message.payment:
            self.logger.warning(f"Message contained no text or payment. Not processing. {message}")
            raise SignalMessageException(f"Message contained no text or payment. Not processing. {message}")
        else:
            try:
                stored_message = Message.objects.create_from_signal(message)
                if message.payment:
                    payment = self._payments.process_signal_payment(stored_message)
                    stored_message.payment = payment
                stored_message.save()
            except Exception as e:
                self.logger.exception("Exception storing message")
            else:
                # In case a message came from a group chat
                group_id = message.group_v2 and message.group_v2.get("id")
                # mark read and get that sweet filled checkbox
                try:
                    if auto_send_receipts and not group_id:
                        self._signal.send_read_receipt(recipient=message.source['number'], timestamps=[message.timestamp])
                except Exception as e:
                    print(e)
                    raise
                return stored_message

    def _done(self, fut: Future[Message]):
        message = fut.result()
        self.logger.info(f"Stored message from {message}")

    def listen(self, auto_send_receipts=True, stop_when_done=False):
        """
        Start the chat.
        :param auto_send_receipts: Send read receipts when we've stored a message in the DB
        :param stop_when_done: If there are no more messages on the iterator, shut down gracefully
        """
        self._run = True
        self.logger.debug("Registering interrupt handler...")
        messages = self._signal.receive_messages()
        with AutoCleanupExecutor(max_workers=4) as pool:
            while self._run:
                try:
                    signal_message = next(messages)
                    self.logger.info(f"Signal received message {signal_message}... Processing!")
                    fut = pool.submit(self._parse_message, signal_message, auto_send_receipts=auto_send_receipts)
                    fut.add_done_callback(self._done)
                except StopIteration:
                    self.logger.error(f"Signal no longer sending messages!")
                    if stop_when_done:
                        print("Stopping")
                        self._run = False
                        return
                    else:
                        time.sleep(0.5)
                except SignalMessageException as e:
                    self.logger.exception(f"Error parsing message from signal")
                except KeyboardInterrupt:
                    self._run = False
                    break



