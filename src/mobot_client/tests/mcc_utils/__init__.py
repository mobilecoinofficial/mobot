# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import uuid
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

import mobilecoin as mc
from mobot_client.payments import MCClient




class MockMCClient(MCClient):

    def __init__(self, *args, **kwargs):
        self.public_address, self.account_id = "foo_address", "foo_account_id"
        self.minimum_fee_pmob = self._get_minimum_fee_pmob()
        self.b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(self.public_address)
        self.logger = logging.getLogger("MCClient")
        self._pool = ThreadPoolExecutor(max_workers=3)
        self._receipt_responses = dict()
        self._txo_responses = dict()

    def _get_minimum_fee_pmob(self) -> int:
        return 1000

    def get_txo(self, txo_id: str) -> dict:
        return self._txo_responses[txo_id]

    def make_receipt(self, amount_pmob: int) -> str:
        '''Creates a receipt to store for later access'''
        receipt = uuid.uuid4()
        txo = uuid.uuid4()
        self._receipt_responses[receipt] = txo
        self._txo_responses[txo] = {
            "object": "receiver_receipt",
            "public_key": b"My Key".hex(),
            "confirmation": b"Confirmation".hex(),
            "tombstone_block": 12345,
            "amount": {
                "object": "amount",
                "commitment": b"Commitment".hex(),
                "masked_value": str(int(amount_pmob)),
            },
        }
        return receipt
