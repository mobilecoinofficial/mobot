# Copyright (c) 2021 MobileCoin. All rights reserved.

from dataclasses import dataclass

from signald_client import Signal


@dataclass
class SignalMessage:
    pass


class MockSignalClient:

    def make_message(self, text, phone_number) -> SignalMessage:
        pass
