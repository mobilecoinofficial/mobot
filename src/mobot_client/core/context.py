# Copyright (c) 2021 MobileCoin. All rights reserved.
import threading
import logging

from mobot_client.models.messages import Message, MessageStatus, ProcessingError

Context = threading.local()


class ContextNotFoundException(Exception):
    """Raise this if no active context is found"""
    pass


def set_context(message: Message):
    Context.message = message


def get_current_context():
    if hasattr(Context, "message"):
        return ChatContext(message=Context.message)
    else:
        raise ContextNotFoundException("No context found for current message!")


def unset_context():
    if hasattr(Context, 'message'):
        del Context.message


class ChatContext:
    def __init__(self, message):
        self._logger = logging.getLogger("MessageContext")
        self.message = message
        self.customer = self.message.customer

    def set_context(self):
        Context.message = self.message

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
        except Exception:
            self._logger.exception("Error leaving message context")
        finally:
            unset_context()





