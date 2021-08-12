# Copyright (c) 2021 MobileCoin. All rights reserved.

import random
import mobilecoin as mc

from decimal import Decimal
from mobot_client.drop_session import BaseDropSession, SessionState
from mobot_client.models import (
    DropSession,
    BonusCoin,
)

from mobot_client.chat_strings import ChatStrings


class AirDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle_airdrop_payment(self, source, customer, amount_paid_mob, drop_session):
        if not self.minimum_coin_available(drop_session.drop):
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.AIRDROP_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
            )
            self.send_mob_to_customer(customer, source, amount_paid_mob, True)
            return

        bonus_coin_objects_for_drop = BonusCoin.objects.filter(drop=drop_session.drop)
        bonus_coins = []

        for bonus_coin in bonus_coin_objects_for_drop:
            number_claimed = DropSession.objects.filter(
                drop=drop_session.drop, bonus_coin_claimed=bonus_coin
            ).count()
            number_remaining = bonus_coin.number_available - number_claimed
            bonus_coins.extend([bonus_coin] * number_remaining)

        if len(bonus_coins) <= 0:
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.BONUS_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
            )
            self.send_mob_to_customer(customer, source, amount_paid_mob, True)
            return

        initial_coin_amount_mob = mc.pmob2mob(
            drop_session.drop.initial_coin_amount_pmob
        )
        random_index = random.randint(0, len(bonus_coins) - 1)
        amount_in_mob = mc.pmob2mob(bonus_coins[random_index].amount_pmob)
        amount_to_send_mob = (
                amount_in_mob
                + amount_paid_mob
                + mc.pmob2mob(self.payments.get_minimum_fee_pmob())
        )
        self.payments.send_mob_to_customer(customer, source, amount_to_send_mob, True)
        drop_session.bonus_coin_claimed = bonus_coins[random_index]
        drop_session.save()
        total_prize = Decimal(initial_coin_amount_mob + amount_in_mob)
        self.messenger.log_and_send_message(
            customer,
            source,
            ChatStrings.REFUND_SENT.format(amount=amount_to_send_mob.normalize(), total_prize=total_prize.normalize())
        )
        self.messenger.log_and_send_message(
            customer, source, ChatStrings.PRIZE.format(prize=total_prize.normalize())
        )
        self.messenger.log_and_send_message(
            customer,
            source,
            ChatStrings.AIRDROP_COMPLETED
        )

        if self.customer_has_store_preferences(customer):
            self.messenger.log_and_send_message(
                customer, source, ChatStrings.BYE
            )
            drop_session.state = SessionState.COMPLETED.value
            drop_session.save()
        else:
            self.messenger.log_and_send_message(
                customer, source, ChatStrings.NOTIFICATIONS_ASK
            )
            drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED.value
            drop_session.save()

    def handle_drop_session_waiting_for_bonus_transaction(self, message, drop_session):
        print("----------------WAITING FOR BONUS TRANSACTION------------------")
        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.AIRDROP_COMMANDS
            )
        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PAY_HELP
            )
        elif message.text.lower() == 'describe':
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.AIRDROP_INSTRUCTIONS
            )
        else:
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.AIRDROP_COMMANDS
            )

        amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)

        value_in_currency = amount_in_mob * Decimal(
            drop_session.drop.conversion_rate_mob_to_currency
        )

        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.AIRDROP_RESPONSE.format(
                amount=amount_in_mob.normalize(),
                symbol=drop_session.drop.currency_symbol,
                value=value_in_currency
            )
        )

    def handle_active_airdrop_drop_session(self, message, drop_session):
        if drop_session.state == SessionState.READY_TO_RECEIVE_INITIAL.value:
            self.handle_drop_session_ready_to_receive(message, drop_session)
            return

        if drop_session.state == SessionState.WAITING_FOR_BONUS_TRANSACTION.value:
            self.handle_drop_session_waiting_for_bonus_transaction(
                message, drop_session
            )
            return

        if drop_session.state == SessionState.ALLOW_CONTACT_REQUESTED.value:
            self.handle_drop_session_allow_contact_requested(message, drop_session)
            return

    def handle_no_active_airdrop_drop_session(self, customer, message, drop):
        if self.customer_has_completed_airdrop(customer, drop):
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.AIRDROP_SUMMARY
            )
            return

        if not customer.phone_number.startswith(drop.number_restriction):
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.COUNTRY_RESTRICTED
            )
            return

        customer_payments_address = self.payments.get_payments_address(message.source)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.PAYMENTS_ENABLED_HELP.format(item_desc=drop.item.description),
            )
            return

        if not self.under_drop_quota(drop):
            self.messenge.log_and_send_message(
                customer, message.source, ChatStrings.OVER_QUOTA
            )
            return

        if not self.minimum_coin_available(drop):
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.NO_COIN_LEFT
            )
            return

        new_drop_session, _ = DropSession.objects.get_or_create(
            customer=customer,
            drop=drop,
            state=SessionState.READY_TO_RECEIVE_INITIAL.value,
        )

        self.messenger.log_and_send_message(
            customer,
            message.source,
            ChatStrings.AIRDROP_DESCRIPTION
        )
        self.messenger.log_and_send_message(
            customer,
            message.source,
            ChatStrings.AIRDROP_INSTRUCTIONS,
        )
        self.messenger.log_and_send_message(customer, message.source, ChatStrings.READY)
