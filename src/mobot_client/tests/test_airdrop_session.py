# Copyright (c) 2021 MobileCoin. All rights reserved.
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional
from unittest import mock
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import mc_util
import pytz
from django.utils import timezone

from mobot_client.chat_strings import ChatStrings
from mobot_client.drop_runner import DropRunner
from mobot_client.models import SessionState, Drop, Customer, DropSession, CustomerStorePreferences
from mobot_client.tests.factories import CustomerFactory, DropFactory, BonusCoinFactory, OldDropFactory
from mobot_client.models.messages import Message, Direction, Payment, SignalPayment, RawSignalMessage
from mobot_client.tests.test_messages import AbstractMessageTest


@dataclass
class ExpectedResponses:
    messages: List[str]
    payments: List[Payment]


class StateResponseTest(AbstractMessageTest):
    def __init__(self, *args, **kwargs):
        self.customer = kwargs.get('customer', CustomerFactory.create())
        self.drop = kwargs.get('drop', DropFactory.create())
        self.incoming_state = kwargs.get('incoming_state')
        self.expected_outgoing_state = kwargs.get('expected_outgoing_state')


class AirDropSessionTest(AbstractMessageTest):

    def _state_response_test(self,
                             customer: Customer,
                             drop: Drop,
                             incoming_message: Optional[str] = None,
                             incoming_payment: Optional[Decimal] = None,
                             incoming_state: Optional[SessionState] = None,
                             expected_responses: List[str] = [],
                             expected_payment: Decimal = None,
                             expected_payment_memo: str = None,
                             expected_fee_coverage: bool = False,
                             expected_outgoing_state: Optional[SessionState] = None, ):
        """A method to create a test to check whether a customer at a given state gets the response expected.
            :param customer: The customer
            :param drop: Drop to test session against
            :param expected_responses: List of messages expected to be sent to customer by MOBot
            :param expected_payment: List of payments expected to be sent by MOBot
            :param expected_payment_memo: Expected memo field for payment
            :
        """

        with mock.patch.object(self.payments, 'send_reply_payment', autospec=True) as send_reply_payment_fn:
            if incoming_state is not None:
                self.logger.info("Creating session state...")
                session = DropSession.objects.create(
                    customer=customer,
                    state=incoming_state,
                    drop=drop,
                )
            if expected_payment is not None:
                signal_payment = SignalPayment.objects.create(
                    note="test",
                    receipt="test_receipt",
                )
                RawSignalMessage.objects.create(
                    account=self.store.phone_number,
                    source=customer.phone_number,
                    payment=signal_payment,
                    timestamp=timezone.now().timestamp(),
                    raw="{}"
                )

                def side_effect(*args, **kwargs):
                    reply_payment = Payment.objects.create(
                        amount_mob=Decimal(expected_payment),
                        customer=customer,
                        txo_id=f"Foo",
                        signal_payment=signal_payment,
                    )

                send_reply_payment_fn.side_effect = side_effect

            self.subscriber = DropRunner(store=self.store, messenger=self.messenger, payments=self.payments)
            if incoming_message:
                self.create_incoming_message(customer=customer, text=incoming_message)
            if incoming_payment:
                self.create_incoming_message(customer=customer, payment_mob=incoming_payment)
            # Process a single message
            self.subscriber.run_chat(process_max=1)
            replies = Message.objects.filter(direction=Direction.SENT)
            self.check_replies(replies, expected_replies=expected_responses)
            if expected_outgoing_state is not None:
                customer.refresh_from_db()
                self.logger.info(
                    f"Verifying customer drop session state matches expected state {expected_outgoing_state}")
                self.assertEqual(customer.state(), expected_outgoing_state.label)
            elif incoming_state is None:
                self.assertIsNone(customer.state())
            if expected_payment is not None:
                self.logger.info(f"Asserting payment of {expected_payment} MOB sent to customer...")
                send_reply_payment_fn.assert_called_once_with(amount_mob=expected_payment,
                                                              cover_transaction_fee=expected_fee_coverage,
                                                              memo=expected_payment_memo)
            else:
                send_reply_payment_fn.assert_not_called()

    def test_can_start_drop(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
        _ = BonusCoinFactory.create(drop=drop)
        self.create_incoming_message(customer=customer, text="Hi")
        # Process a single message
        expected_responses = [
            ChatStrings.AIRDROP_DESCRIPTION,
            ChatStrings.AIRDROP_INSTRUCTIONS,
            ChatStrings.READY
        ]
        self._state_response_test(customer,
                                  drop,
                                  expected_responses=expected_responses,
                                  expected_outgoing_state=SessionState.READY)

    def test_closed(self):
        ### OldDropFactory creates an expired drop
        customer = CustomerFactory.create()
        drop = OldDropFactory.create(store=self.store)
        self.create_incoming_message(customer=customer, text="Hi")
        expected_responses = [
            ChatStrings.STORE_CLOSED_SHORT,
        ]
        self._state_response_test(customer, drop, expected_responses=expected_responses)

    def test_closed_but_advertising(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store,
                                  advertisment_start_time=timezone.now() - timedelta(days=1),
                                  start_time=timezone.now() + timedelta(days=2),
                                  end_time=timezone.now() + timedelta(days=4))
        self.create_incoming_message(customer=customer, text="Hi")
        bst_time = drop.start_time.astimezone(
            pytz.timezone(drop.timezone)
        )
        response_message = ChatStrings.STORE_CLOSED.format(
            date=bst_time.strftime("%A, %b %d"),
            time=bst_time.strftime("%-I:%M %p %Z"),
            desc=drop.pre_drop_description
        )
        expected_responses = [
            response_message,
        ]
        self._state_response_test(customer, drop, expected_responses=expected_responses)

    def test_country_code_mismatch(self):
        customer = CustomerFactory.create(phone_number="+18055551212")
        drop = DropFactory.create(number_restriction="+44")
        bonus = BonusCoinFactory.create(drop=drop)
        expected_responses = [
            ChatStrings.COUNTRY_RESTRICTED
        ]
        self._state_response_test(customer, drop, incoming_message="Hi", expected_responses=expected_responses)

    def test_initial_payment_sent(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(initial_coin_amount_mob=Decimal("0.1"))
        BonusCoinFactory.create(drop=drop)

        expected_message = ChatStrings.AIRDROP_INITIALIZE.format(
            amount=drop.initial_coin_amount_mob.normalize(),
            symbol=drop.currency_symbol,
            value=drop.value_in_currency(drop.initial_coin_amount_mob))
        self._state_response_test(customer,
                                  drop,
                                  incoming_message="y",
                                  incoming_state=SessionState.READY,
                                  expected_responses=[expected_message],
                                  expected_payment=Decimal('1e-1'),
                                  expected_fee_coverage=True,
                                  expected_payment_memo="Initial coins",
                                  expected_outgoing_state=SessionState.WAITING_FOR_PAYMENT)

    def test_customer_ready_answer(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create()
        BonusCoinFactory.create(drop=drop)

        expected_responses = [
            ChatStrings.YES_NO_HELP,
        ]

        self._state_response_test(customer,
                                  drop,
                                  incoming_message="foo",
                                  incoming_state=SessionState.READY,
                                  expected_responses=expected_responses)

    def _test_bonus_payment_sent(self, has_store_preferences: bool = False):
        coin_amt = Decimal("1.0")
        initial_amt = Decimal("0.1")
        customer_sent_amount = Decimal("0.01")
        customer = CustomerFactory.create()
        drop = DropFactory.create(initial_coin_amount_mob=initial_amt)
        BonusCoinFactory.create(amount_mob=coin_amt, drop=drop)
        total_prize = customer_sent_amount + coin_amt + initial_amt
        # Expect the customer to get back the amount they sent, the fee they paid, and the prize
        prize_and_sent_with_fee = coin_amt + customer_sent_amount + self.payments.minimum_fee_mob

        expected_state = SessionState.ALLOW_CONTACT_REQUESTED

        if has_store_preferences:
            CustomerStorePreferences.objects.create(store=self.store, customer=customer, allows_contact=False)
            expected_state = SessionState.COMPLETED
            expected_goodbye = ChatStrings.BYE
        else:
            expected_goodbye = ChatStrings.FUTURE_ALERTS

        expected_responses = [
            ChatStrings.PAYMENT_RECEIVED,
            ChatStrings.REFUND_SENT.format(amount=total_prize - initial_amt, total_prize=initial_amt + coin_amt),
            ChatStrings.PRIZE.format(prize=coin_amt + initial_amt),
            ChatStrings.AIRDROP_COMPLETED,
            expected_goodbye,
        ]

        self._state_response_test(customer, drop,
                                  incoming_payment=customer_sent_amount,
                                  incoming_state=SessionState.WAITING_FOR_PAYMENT,
                                  expected_responses=expected_responses,
                                  expected_payment=prize_and_sent_with_fee,
                                  expected_payment_memo="Bonus",
                                  expected_fee_coverage=True,
                                  expected_outgoing_state=expected_state)

    def test_can_complete_drop_and_ask_for_contact(self):
        self._test_bonus_payment_sent()

    def test_can_complete_drop_and_say_bye(self):
        self._test_bonus_payment_sent(has_store_preferences=True)

    def test_over_quota(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create()
        ## Without Bonus Coins, we'll be over quota
        self._state_response_test(customer, drop,
                                  incoming_message="Hi",
                                  expected_responses=[ChatStrings.OVER_QUOTA])

    def test_out_of_funds(self):
        with mock.patch.object(self.payments, 'get_unspent_pmob') as get_unspent_pmob_fn:
            customer = CustomerFactory.create()
            drop = DropFactory.create()
            get_unspent_pmob_fn.return_value = 0
            self._state_response_test(customer, drop, incoming_message="yes", incoming_state=SessionState.READY,
                                      expected_responses=[ChatStrings.OVER_QUOTA])

    def test_out_of_funds_at_bonus(self):
        with mock.patch.object(self.payments, 'get_unspent_pmob') as get_unspent_pmob_fn:
            customer = CustomerFactory.create()
            drop = DropFactory.create()
            get_unspent_pmob_fn.return_value = 0
            customer_sent_amount = Decimal("0.1")
            self._state_response_test(
                customer, drop,
                incoming_payment=customer_sent_amount,
                incoming_state=SessionState.WAITING_FOR_PAYMENT,
                expected_responses=[
                    ChatStrings.PAYMENT_RECEIVED,
                    ChatStrings.BONUS_SOLD_OUT_REFUND.format(amount=customer_sent_amount)
                ],
                expected_fee_coverage=True,
                expected_payment_memo="Refund - Sold Out",
                expected_payment=customer_sent_amount
            )

    def test_unsolicited_payment(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create()
        customer_sent_amount = Decimal("0.1")
        self._state_response_test(customer, drop,
                                  incoming_state=SessionState.READY,
                                  incoming_payment=customer_sent_amount,
                                  expected_responses=[
                                      ChatStrings.PAYMENT_RECEIVED,
                                      ChatStrings.UNSOLICITED_PAYMENT,
                                  ],
                                  expected_payment=customer_sent_amount,
                                  expected_fee_coverage=False,
                                  expected_payment_memo="Unsolicited payment refund", )

    def _test_commands_at_awaiting(self, command: str):
        customer = CustomerFactory.create()
        drop = DropFactory.create()
        BonusCoinFactory.create(drop=drop)
        first_response = None

        if command == "describe":
            first_response = ChatStrings.AIRDROP_INSTRUCTIONS
        elif command == "pay":
            first_response = ChatStrings.PAY_HELP
        elif command == "help":
            first_response = ChatStrings.AIRDROP_COMMANDS

        self._state_response_test(customer, drop,
                                  incoming_state=SessionState.WAITING_FOR_PAYMENT,
                                  incoming_message=command,
                                  expected_responses=[
                                      first_response,
                                      ChatStrings.AIRDROP_RESPONSE.format(
                                          amount=drop.initial_coin_amount_mob.normalize(),
                                          symbol=drop.currency_symbol,
                                          value=drop.initial_coin_amount_value_in_currency
                                      )
                                  ])

    def test_pay_at_awaiting(self):
        self._test_commands_at_awaiting("pay")

    def test_help_at_awaiting(self):
        self._test_commands_at_awaiting("help")

    def test_describe_at_awaiting(self):
        self._test_commands_at_awaiting("describe")

