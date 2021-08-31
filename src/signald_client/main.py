# Copyright (c) 2021 MobileCoin. All rights reserved.
# This code is copied from [pysignald](https://pypi.org/project/pysignald/) and modified to run locally with payments
import logging
import re
import signal
import sys

from signald import Signal as _Signal

# We'll need to know the compiled RE object later.
RE_TYPE = type(re.compile(""))


class Signal(_Signal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("SignalListener")
        self._chat_handlers = []
        self._payment_handlers = []
        self._run = True

    def isolated_handler(self, func):
        def isolated(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                self.logger.exception(f"Chat exception while processing: {func.__name__}({args}, {kwargs})")
                print("Signal hit exception.")
        return isolated

    def register_handler(self, regex, func, order=100):
        self.logger.info(f"Registering chat handler for {regex if regex else 'default'}")
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)

        self._chat_handlers.append((order, regex, self.isolated_handler(func)))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def chat_handler(self, regex, order=100):
        """
        A decorator that registers a chat handler function with a regex.
        """
        def decorator(func):
            self.register_handler(regex, func, order)
            return func

        return decorator

    def payment_handler(self, func):
        isolated = self.isolated_handler(func)
        self._payment_handlers.append(isolated)
        return isolated

    def register_payment_handler(self, func):
        self.payment_handler(func)

    def _stop_handler(self, sig, frame):
        self.logger.error(f"SIGNAL {sig} CALLED! Finishing up current message...")
        self._run = False
        sys.exit(0)

    def run_chat(self, auto_send_receipts=False):
        """
        Start the chat event loop.
        """
        signal.signal(signal.SIGINT, self._stop_handler)
        signal.signal(signal.SIGQUIT, self._stop_handler)
        messages_iterator = self.receive_messages()
        while self._run:
            message = next(messages_iterator)
            print("Receiving message")
            print(message)

            if message.payment:
                for func in self._payment_handlers:
                    func(message.source, message.payment)
                continue

            if not message.text:
                continue

            for _, regex, func in self._chat_handlers:
                match = re.search(regex, message.text)
                if not match:
                    continue

                try:
                    reply = func(message, match)
                except Exception as e:  # noqa - We don't care why this failed.
                    print(e)
                    raise
                    continue

                if isinstance(reply, tuple):
                    stop, reply = reply
                else:
                    stop = True

                # In case a message came from a group chat
                group_id = message.group_v2 and message.group_v2.get("id")  # TODO - not tested

                # mark read and get that sweet filled checkbox
                try:
                    if auto_send_receipts and not group_id:
                        self.send_read_receipt(recipient=message.source['number'], timestamps=[message.timestamp])

                    if group_id:
                        self.send_group_message(recipient_group_id=group_id, text=reply)
                    else:
                        self.send_message(recipient=message.source['number'], text=reply)
                except Exception as e:
                    print(e)
                    raise

                if stop:
                    # We don't want to continue matching things.
                    break
        return
