# Copyright (c) 2021 MobileCoin. All rights reserved.
import threading
import logging

from mobot_client.models.messages import Message


Context = threading.local()


class CurrentContext:
    def __init__(self):
        self.message = None
        if hasattr(Context, 'message'):
            self.message = Context.message
            self.customer = self.message.customer

    def set_context(self, message: Message):
        Context.message = message
        self.message = message


def get_context():
    return CurrentContext()


def set_context(message: Message):
    Context.message = message


def unset_context():
    if hasattr(Context, 'message'):
        del Context.message

