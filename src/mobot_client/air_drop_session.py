# Copyright (c) 2021 MobileCoin. All rights reserved.

import random

from decimal import Decimal

from django.db import transaction

from mobot_client.drop_session import BaseDropSession
from mobot_client.models import (
    Drop,
    DropSession,
    BonusCoin, SessionState, OutOfStockException, Customer,
)

import mobilecoin as mc
from mobot_client.chat_strings import ChatStrings
from mobot_client.models.messages import Message
from mobot_client.payments import NotEnoughFundsException


class AirDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initial_coin_funds_available(self, drop: Drop) -> bool:
        return self.payments.has_enough_funds_for_payment(drop.initial_coin_amount_pmob)

    def bonus_coin_funds_available(self, drop_session: DropSession) -> bool:
        return self.payments.has_enough_funds_for_payment(drop_session.bonus_coin_claimed.amount_pmob)

    def handle_airdrop_payment(self, source, customer, amount_paid_mob, drop_session: DropSession):
        refunded = False
        try:
            claimed_coin: BonusCoin = BonusCoin.objects.claim_random_coin(drop_session)
            if not self.bonus_coin_funds_available(drop_session):
                self.messenger.log_and_send_message(
                    customer,
                    ChatStrings.AIRDROP_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
                )
                self.payments.send_reply_payment(customer, amount_paid_mob, True)
                refunded = True
                raise NotEnoughFundsException("Not enough MOB in wallet to cover bonus coin")
            ###  This will stop us from sending an initial payment if bonus coins aren't available
        except (OutOfStockException, NotEnoughFundsException) as e:
            self.logger.exception(f"Could not fulfill drop to customer {customer.source}")
            if not refunded:
                self.messenger.log_and_send_message(
                    customer,
                    ChatStrings.BONUS_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
                )
                self.payments.send_reply_payment(customer, amount_paid_mob, True)
        else:
            initial_coin_amount_mob = mc.pmob2mob(
                drop_session.drop.initial_coin_amount_pmob
            )
            amount_in_mob = mc.pmob2mob(claimed_coin.amount_pmob)
            amount_to_send_mob = (
                    amount_in_mob
                    + amount_paid_mob
                    + mc.pmob2mob(self.payments.get_minimum_fee_pmob())
            )
            self.payments.send_reply_payment(customer, amount_to_send_mob, True)

            total_prize = Decimal(initial_coin_amount_mob + amount_in_mob)

            self.messenger.log_and_send_message(
                customer,
                ChatStrings.REFUND_SENT.format(amount=amount_to_send_mob.normalize(), total_prize=total_prize.normalize())
            )
            self.messenger.log_and_send_message(
                customer, ChatStrings.PRIZE.format(prize=total_prize.normalize())
            )
            self.messenger.log_and_send_message(
                customer,
                ChatStrings.AIRDROP_COMPLETED
            )

            if customer.has_store_preferences(store=self.store):
                self.messenger.log_and_send_message(
                    customer, ChatStrings.BYE
                )
                drop_session.state = SessionState.COMPLETED
                drop_session.save()
            else:
                self.messenger.log_and_send_message(
                    customer, ChatStrings.NOTIFICATIONS_ASK
                )
                drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED
                drop_session.save()

    def handle_airdrop_session_ready_to_receive(self, message, drop_session):
        """Ask if the customer is ready to receive MOB.
           If the customer replies in the affirmative, we send them the original MOB.
        """
        if (
                message.text.lower() == "n"
                or message.text.lower() == "no"
                or message.text.lower() == "cancel"
        ):
            drop_session.state = SessionState.CANCELLED
            self.messenger.log_and_send_message(
                drop_session.customer,
                ChatStrings.SESSION_CANCELLED
            )
        elif message.text.lower() == "y" or message.text.lower() == "yes":
            if not self.under_drop_quota(drop_session.drop):
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    ChatStrings.AIRDROP_OVER
                )
                drop_session.state = SessionState.CANCELLED
            elif not self.initial_coin_funds_available(drop_session.drop):
                self.messenger.log_and_send_message(
                    ChatStrings.AIRDROP_OVER
                )
                drop_session.state = SessionState.CANCELLED
            else:
                amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
                value_in_currency = amount_in_mob * Decimal(
                    drop_session.drop.conversion_rate_mob_to_currency
                )
                self.logger.info(f"Sending customer {drop_session.customer} initial coin amount...")
                self.payments.send_reply_payment(amount_in_mob, True)
                self.messenger.log_and_send_message(
                    ChatStrings.AIRDROP_INITIALIZE.format(
                        amount=amount_in_mob.normalize(),
                        symbol=drop_session.drop.currency_symbol,
                        value=value_in_currency
                    )
                )
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    ChatStrings.PAY_HELP
                )
                drop_session.state = SessionState.WAITING_FOR_PAYMENT
        else:
            self.messenger.log_and_send_message(
                ChatStrings.YES_NO_HELP
            )
        drop_session.save()

    def handle_drop_session_waiting_for_bonus_transaction(self, message, drop_session):
        print("----------------WAITING FOR BONUS TRANSACTION------------------")
        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                ChatStrings.AIRDROP_COMMANDS
            )
        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(
                ChatStrings.PAY_HELP
            )
        elif message.text.lower() == 'describe':
            self.messenger.log_and_send_message(
                ChatStrings.AIRDROP_INSTRUCTIONS
            )
        else:
            self.messenger.log_and_send_message(
                ChatStrings.AIRDROP_COMMANDS
            )

        amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)

        value_in_currency = amount_in_mob * Decimal(
            drop_session.drop.conversion_rate_mob_to_currency
        )

        self.messenger.log_and_send_message(
            ChatStrings.AIRDROP_RESPONSE.format(
                amount=amount_in_mob.normalize(),
                symbol=drop_session.drop.currency_symbol,
                value=value_in_currency
            )
        )

    def handle_active_airdrop_drop_session(self, message: Message, drop_session: DropSession):
        if drop_session.state == SessionState.READY:
            self.handle_airdrop_session_ready_to_receive(message, drop_session)
        elif drop_session.state == SessionState.WAITING_FOR_PAYMENT:
            self.handle_drop_session_waiting_for_bonus_transaction(
                message, drop_session
            )
        elif drop_session.state == SessionState.ALLOW_CONTACT_REQUESTED:
            self.handle_drop_session_allow_contact_requested(message, drop_session)

    def handle_no_active_airdrop_drop_session(self, customer: Customer, message: Message, drop: Drop):
        if customer.has_completed_drop(drop):
            self.messenger.log_and_send_message(ChatStrings.AIRDROP_SUMMARY)

        elif customer.has_completed_drop_with_error(drop):
            self.messenger.log_and_send_message(
                ChatStrings.AIRDROP_INCOMPLETE_SUMMARY
            )
        elif not customer.matches_country_code_restriction(drop):
            self.messenger.log_and_send_message(
                ChatStrings.COUNTRY_RESTRICTED
            )
        else:
            customer_payments_address = self.payments.get_payments_address(customer.phone_number.as_e164)
            if customer_payments_address is None:
                self.messenger.log_and_send_message(
                ChatStrings.COUNTRY_RESTRICTED
            )
            else:
                customer_payments_address = self.payments.get_payments_address(customer.phone_number.as_e164)
                if customer_payments_address is None:
                    self.messenger.log_and_send_message(
                        ChatStrings.PAYMENTS_ENABLED_HELP.format(item_desc=drop.pre_drop_description),
                    )
                elif not drop.under_quota():
                    self.messenger.log_and_send_message(
                        ChatStrings.OVER_QUOTA
                    )
                elif not self.initial_coin_funds_available(drop):
                    self.messenger.log_and_send_message(
                        ChatStrings.NO_COIN_LEFT
                    )
                    raise NotEnoughFundsException("Not enough MOB in wallet to cover initial payment")
                else:
                    new_drop_session, _ = DropSession.objects.get_or_create(
                        customer=customer,
                        drop=drop,
                        state=SessionState.READY,
                    )

                    self.messenger.log_and_send_message(
                        ChatStrings.AIRDROP_DESCRIPTION
                    )
                    self.messenger.log_and_send_message(
                        ChatStrings.AIRDROP_INSTRUCTIONS,
                    )
                    self.messenger.log_and_send_message(ChatStrings.READY)
