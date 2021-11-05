# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
A command to send funds to customers, with a friendly apology if necessary
"""
import decimal
from logging import getLogger
from argparse import ArgumentParser


from django.core.management.base import BaseCommand
from django.conf import settings

from signald import Signal

from mobot_client.concurrency import AutoCleanupExecutor
from mobot_client.core.context import ChatContext
from mobot_client.logger import SignalMessenger
from mobot_client.chat_strings import ChatStrings
from mobot_client.models import Customer, ChatbotSettings
from mobot_client.models.messages import Message, Direction, Payment, MessageStatus
from mobot_client.payments import Payments
from mobot_client.payments.client import MCClient
from mobot_client.utils import TimerFactory


class Command(BaseCommand):
    help = 'Send MOB to Customer'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        store = ChatbotSettings.load().store
        signal = Signal(
            store.phone_number.as_e164, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT))
        )
        self.logger = getLogger("SpeedTest")
        self.messenger = SignalMessenger(signal, store)
        mcc = MCClient()
        self.payments = Payments(
            mcc,
            store,
            self.messenger,
            signal,
        )

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '-c',
            '--customer',
            help="A customer phone number",
            required=True,
            type=str,
        )
        parser.add_argument(
            '-m',
            '--mob',
            required=False,
            type=decimal.Decimal,
            help='Amount of MOB to send',
            default=decimal.Decimal("0.1"),
        )
        parser.add_argument(
            '-t',
            '--text',
            default=ChatStrings.APOLOGIES_HAVE_SOME_MOB,
            type=str,
            help='Text to send customers'
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=8,
            help='Memo to add to signal payment receipt'
        )
        parser.add_argument(
            '-n',
            '--number',
            type=int,
            default=50,
        )

    def reply_context(self, customer: Customer):
        bogus_message = Message.objects.create(
            customer=customer,
            text="",
            store=ChatbotSettings.load().store,
            direction=Direction.RECEIVED,
            status=MessageStatus.PROCESSING,
        )
        return ChatContext(message=bogus_message)

    def handle(self, *args, **kwargs):
        mob = kwargs['mob']
        threads = kwargs['threads']
        number = kwargs['number']
        customer = Customer.objects.get(phone_number=kwargs['customer'])

        def done_callback(fut):
            self.logger.info(fut.result())
            self.logger.info("Paid out to customer")

        def pay_with_context(num) -> Payment:
            with self.reply_context(customer) as _:
                return self.payments.send_reply_payment(
                    amount_mob=mob,
                    cover_transaction_fee=True,
                    memo=f"speed test {num}")

        timers = TimerFactory("ReplySpeed", self.logger)
        with timers.get_timer("TestPaymentReplySpeed"):
            with AutoCleanupExecutor(max_workers=threads) as pool:
                for payment in range(number):
                    fut = pool.submit(pay_with_context, payment)
                    fut.add_done_callback(done_callback)
                    self.logger.info(f"Paid out payment number {number}")
        self.logger.exception(f"Payment to Customer {customer.phone_number.as_e164} of {mob} MOB failed!")
        self.logger.info(f"Payment to customer {customer.phone_number.as_e164} succeeded!")
