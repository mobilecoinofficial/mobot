# Copyright (c) 2021 MobileCoin. All rights reserved.
from __future__ import annotations
import threading
import logging

from django.db import connection
from mobot_client.models.messages import Message, MessageStatus, ProcessingError

Context = threading.local()


class ContextNotFoundException(Exception):
    """Raise this if no active context is found"""
    pass


def get_current_context():
    if hasattr(Context, "current"):
        return Context.current
    else:
        raise ContextNotFoundException("No current context for this thread")


class ChatContext:
    def __init__(self, message: Message):
        self._logger = logging.getLogger("MessageContext")
        self.message = message
        self.customer = self.message.customer
        self.set_context()

    @staticmethod
    def get_current_context() -> ChatContext:
        if hasattr(Context, "current"):
            return Context.current
        else:
            raise ContextNotFoundException("No current context for this thread")

    def set_context(self):
        Context.current = self

    def unset_context(self):
        if hasattr(Context, 'current'):
            del Context.current

    def __enter__(self):
        self.set_context()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.info("Leaving message response context")
        try:
            if exc_type:
                self.message.status = MessageStatus.ERROR
                ProcessingError.objects.create(
                    message=self.message,
                    exception=str(exc_type),
                    tb=str(exc_tb)
                )
            else:
                self.message.status = MessageStatus.PROCESSED
            self.message.save()
        except Exception as e:
            self._logger.exception("Error leaving message context")
            raise e
        finally:
            try:
                connection.close()
            except Exception as e:
                self._logger.exception("Exception closing DB connection")
            self.unset_context()





