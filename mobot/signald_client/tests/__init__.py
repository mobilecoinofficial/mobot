import pytest
from unittest import mock

from decimal import Decimal
from uuid import uuid4

from mobot.signald_client.types import Message


def produce_message(text_base: str = "Hello ", source="+447441433907", payment_amt: Decimal = 0) -> Message:
    payment = None if not payment_amt else dict(
        txo_public_key="A_public_key!",
        txo_confirmation="SomeConfirmation",
        amount_commitment=str(payment_amt),
        amount_masked=str(payment_amt),
    )
    return Message(
        username="Greg",
        source=source,
        payment=payment,
        text=f"{text_base} + {uuid4()}"
    )


def produce_messages(num_messages=10):
    for _ in range(num_messages):
        yield produce_message()