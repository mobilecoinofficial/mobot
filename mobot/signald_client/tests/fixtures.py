from decimal import Decimal
from uuid import uuid4
from enum import Enum

import pytest
from unittest import mock
from mobot.signald_client import Signal

from ..types import Message

DEFAULT_STORE_PHONE = "+447441433907"


@pytest.fixture(scope="class")
def mocked_worker():
    with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages()) as mock_method:
        yield Signal(DEFAULT_STORE_PHONE)


def produce_message(text_base: str = "Hello ", source=DEFAULT_STORE_PHONE, payment_amt: Decimal = 0) -> Message:
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