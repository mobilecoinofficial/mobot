# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the Django runserver command.
"""
import decimal
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
    help = 'Run MOBot Client'

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout, stderr, no_color, force_color)
        store = ChatbotSettings.load().store
        signal = Signal(
            store.phone_number, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT))
        )
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

    def handle(self, *args, **kwargs):
        mob = kwargs['mob']
        print(kwargs)
        customers = Customer.objects.filter(phone_number__in=kwargs['customer_phone_numbers'])
        message_text = kwargs.get('text').format(mob=mob)
        for customer in customers:
            self.messenger.log_and_send_message(customer, str(customer.phone_number), message_text)
            self.payments.send_mob_to_customer(customer=customer,
                                               source=str(customer.phone_number),
                                               amount_mob=mob,
                                               cover_transaction_fee=False)
