# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
A command to send funds to customers, with a friendly apology if necessary
"""
import decimal
from logging import getLogger
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.conf import settings

from signald_client import Signal
from mobot_client.logger import SignalMessenger
from mobot_client.chat_strings import ChatStrings
from mobot_client.models import Customer, ChatbotSettings
from mobot_client.payments import Payments
from mobot_client.payments.client import MCClient


class Command(BaseCommand):
    help = 'Send MOB to Customer'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        store = ChatbotSettings.load().store
        signal = Signal(
            store.phone_number.as_e164, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT))
        )
        self.logger = getLogger("SendMobToCustomer")
        self.messenger = SignalMessenger(signal, store)
        mcc = MCClient()
        self.payments = Payments(
            mcc,
            mcc.minimum_fee_pmob,
            mcc.account_id,
            store,
            self.messenger,
            signal,
        )

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '-c',
            '--customer-phone-numbers',
            help="A list of customer phone numbers separated by commas",
            required=True,
            type=lambda s: [str(customer) for customer in s.replace(' ', '').split(',')])
        parser.add_argument(
            '-m',
            '--mob',
            required=True,
            type=decimal.Decimal,
            help='Amount of MOB to send'
        )
        parser.add_argument(
            '-t',
            '--text',
            default=ChatStrings.APOLOGIES_HAVE_SOME_MOB,
            type=str,
            help='Text to send customers'
        )
        parser.add_argument(
            '--memo',
            default='BonusCoin',
            help='Memo to add to signal payment receipt'
        )
        parser.add_argument(
            '-f',
            '--cover-fee',
            action='store_true',
            default=False
        )

    def handle(self, *args, **kwargs):
        mob = kwargs['mob']
        memo = kwargs['memo']
        cover_fee = kwargs['cover_fee']
        customers = Customer.objects.filter(phone_number__in=kwargs['customer_phone_numbers'])
        message_text = kwargs['text'].format(mob=mob)

        for customer in customers:
            customer_phone_number = customer.phone_number.as_e164
            self.messenger.log_and_send_message(customer, customer_phone_number, message_text)
            try:
                self.payments.send_mob_to_customer(customer=customer,
                                                   source=customer_phone_number,
                                                   amount_mob=mob,
                                                   cover_transaction_fee=cover_fee,
                                                   memo=memo)
            except Exception as e:
                self.logger.exception(f"Payment to Customer {customer.phone_number.as_e164} of {mob} MOB failed!")
            self.logger.info(f"Payment to customer {customer.phone_number.as_e164} succeeded!")
