# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
A command to send funds to customers, with a friendly apology if necessary
"""
import decimal
from logging import getLogger
from argparse import ArgumentParser
import time
import itertools
import random
from typing import List
import json
import sys

from django.core.management.base import BaseCommand
from django.conf import settings

from signald import Signal

from mobot_client.concurrency import AutoCleanupExecutor
from mobot_client.core.context import ChatContext
from mobot_client.logger import SignalMessenger
from mobot_client.chat_strings import ChatStrings
from mobot_client.models import Customer, ChatbotSettings
from mobot_client.models.messages import Message, Direction, Payment
from mobot_client.payments import Payments
from mobot_client.payments.client import MCClient
from mobot_client.utils import TimerFactory
import mc_util



class Command(BaseCommand):
    help = 'Split txos'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        store = ChatbotSettings.load().store
        signal = Signal(
            store.phone_number.as_e164, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT))
        )
        self.logger = getLogger("Split Txos")
        self.messenger = SignalMessenger(signal, store)
        self.mcc = MCClient()
        self.payments = Payments(
            self.mcc,
            store,
            self.messenger,
            signal,
        )

    def _load_account_prefix(self, prefix):
        accounts = self.mcc.get_all_accounts()
        matching_ids = [
            a_id for a_id in accounts.keys()
            if a_id.startswith(prefix)
        ]
        if len(matching_ids) == 0:
            print('Could not find account starting with', prefix)
            exit(1)
        elif len(matching_ids) == 1:
            account_id = matching_ids[0]
            return accounts[account_id]
        else:
            print('Multiple matching matching ids: {}'.format(', '.join(matching_ids)))
            exit(1)

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '-m',
            '--mob',
            required=False,
            type=decimal.Decimal,
            help='Amount of MOB to send',
            default=decimal.Decimal("0.105"),
        )
        parser.add_argument(
            '-t',
            '--num-txos',
            type=int,
            default=25,
        )
        parser.add_argument(
            '-a',
            '--source-account',
            type=str,
            required=True,
            default="2cf3d1"
        )
        parser.add_argument(
            '-x',
            '--split',
            action='store_true',
            default=False,
        )

    def reply_context(self, customer: Customer):
        bogus_message = Message.objects.create(
            customer=customer,
            text="",
            store=ChatbotSettings.load().store,
            direction=Direction.RECEIVED,
        )
        return ChatContext(message=bogus_message)

    def cleanup_accounts(self, source_account, source_address: str):
        fee = self.mcc.minimum_fee_pmob
        for account in self.mcc.get_all_accounts():
            self.logger.info(f"Found account {account}")
            if account == source_account:
                continue
            balance = int(self.mcc.get_balance_for_account(account)['unspent_pmob'])
            if not balance > 0:
                self.logger.info(f"Removing account {account}")
                self.mcc.remove_account(account)
            else:
                print(f"Sending all {balance} MOB back from {account} to source {source_address}")
                self.mcc.build_and_submit_transaction(account, mc_util.pmob2mob(balance - fee), source_address)
                self.mcc.remove_account(account)

    def handle(self, *args, **kwargs):
        mob = kwargs['mob']
        num_txos = kwargs['num_txos']
        source = kwargs['source_account']
        source_info = self._load_account_prefix(source)
        source_account = source_info['account_id']
        split = kwargs['split']

        if split:
            self.mcc.split_txos(source_account, split_size_mob=mob, num_splits=num_txos)
        else:
            unsplit = list(self.mcc.get_all_unspent_txos_for_account(source_account))
            self.logger.info(f"Total number of unsplit TXOs: {len(unsplit)}")
