# Copyright (c) 2021 MobileCoin. All rights reserved.

from mobilecoin.utility import b58_wrapper_to_b64_public_address
from mobilecoin import Client as MCC

from django.conf import settings


class MCClient(MCC):
    def __init__(self):
        super().__init__(settings.FULLSERVICE_URL)
        self.public_address, self.account_id = self._get_default_account_info()
        self.minimum_fee_pmob = self._get_minimum_fee_pmob()
        self.b64_public_address = b58_wrapper_to_b64_public_address(self.public_address)

    def _get_minimum_fee_pmob(self):
        get_network_status_response = self.get_network_status()
        return int(get_network_status_response["fee_pmob"])

    def _get_default_account_info(self) -> (str, str):
        accounts = self.get_all_accounts()
        account_id = next(iter(accounts))
        account_obj = accounts[account_id]
        public_address = account_obj["main_address"]
        return public_address, account_id
