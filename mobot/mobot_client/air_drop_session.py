# Copyright (c) 2021 MobileCoin. All rights reserved.

import random
import full_service_cli as mc

from decimal import Decimal
from mobot_client.drop_session import BaseDropSession, SessionState
from mobot_client.models import Customer, DropSession, CustomerStorePreferences, BonusCoin, Order, Sku


class AirDropSession(BaseDropSession):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle_airdrop_payment(self, source, customer, amount_paid_mob, drop_session):
        if not self.minimum_coin_available(drop_session.drop):
            self.messenger.log_and_send_message(customer, source,
                                 f"Thank you for sending {amount_paid_mob.normalize()} MOB! Unfortunately, we ran out of MOB to distribute 😭. We're returning your MOB and the network fee.")
            self.send_mob_to_customer(source, amount_paid_mob, True)
            return

        bonus_coin_objects_for_drop = BonusCoin.objects.filter(drop=drop_session.drop)
        bonus_coins = []

        for bonus_coin in bonus_coin_objects_for_drop:
            number_claimed = DropSession.objects.filter(drop=drop_session.drop, bonus_coin_claimed=bonus_coin).count()
            number_remaining = bonus_coin.number_available - number_claimed
            bonus_coins.extend([bonus_coin] * number_remaining)

        if len(bonus_coins) <= 0:
            self.messenger.log_and_send_message(customer, source,
                                 f"Thank you for sending {amount_paid_mob.normalize()} MOB! Unfortunately, we ran out of bonuses 😭. We're returning your MOB and the network fee.")
            self.send_mob_to_customer(source, amount_paid_mob, True)
            return

        initial_coin_amount_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
        random_index = random.randint(0, len(bonus_coins) - 1)
        amount_in_mob = mc.pmob2mob(bonus_coins[random_index].amount_pmob)
        amount_to_send_mob = amount_in_mob + amount_paid_mob + mc.pmob2mob(self.payments.get_minimum_fee_pmob())
        self.send_mob_to_customer(source, amount_to_send_mob, True)
        drop_session.bonus_coin_claimed = bonus_coins[random_index]
        drop_session.save()
        total_prize = Decimal(initial_coin_amount_mob + amount_in_mob)
        self.messenger.log_and_send_message(customer, source,
                             f"We've sent you back {amount_to_send_mob.normalize()} MOB! That brings your total prize to {total_prize.normalize()} MOB")
        self.messenger.log_and_send_message(customer, source, f"Enjoy your {total_prize.normalize()} MOB!")
        self.messenger.log_and_send_message(customer, source,
                             "You've completed the MOB Coin Drop! To give others a chance, we're only allowing one MOB airdrop per person")

        if self.customer_has_store_preferences(customer):
            self.messenger.log_and_send_message(customer, source, "Thanks! MOBot OUT. Buh-bye")
            drop_session.state = SessionState.COMPLETED.value
            drop_session.save()
        else:
            self.messenger.log_and_send_message(customer, source, "Would you like to receive alerts for future drops?")
            drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED.value
            drop_session.save()

    def handle_drop_session_waiting_for_bonus_transaction(self, message, drop_session):
        print("----------------WAITING FOR BONUS TRANSACTION------------------")
        if message.text.lower() == "help":
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                 "Commands available are:\n\n?\tQuick list of commands\nhelp\tList of command and what they do\ndescribe\tDescription of drop\npay\tHow to pay")
        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                 "To see your balance and send a payment:\n\n1. Select the attachment icon and select Pay\n\n2. Enter the amount you want to send (e.g. 0.01 MOB)\n\n3. Tap Pay\n\n4. Tap Confirm Payment")
        else:
            self.messenger.log_and_send_message(drop_session.customer, message.source, "Commands are ?, help, describe, and pay\n\n")

        amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)

        value_in_currency = amount_in_mob * Decimal(drop_session.drop.conversion_rate_mob_to_currency)

        self.messenger.log_and_send_message(drop_session.customer, message.source,
                             f"We've sent you {amount_in_mob.normalize()} MOB (~{drop_session.drop.currency_symbol}{value_in_currency:.2f}). Send us 0.01 MOB, and we'll send it back, plus more! You could end up with as much as £50 of MOB")

    def handle_active_airdrop_drop_session(self, message, drop_session):
        if drop_session.state == SessionState.READY_TO_RECEIVE_INITIAL.value:
            self.handle_drop_session_ready_to_receive(message, drop_session)
            return

        if drop_session.state == SessionState.WAITING_FOR_BONUS_TRANSACTION.value:
            self.handle_drop_session_waiting_for_bonus_transaction(message, drop_session)
            return

        if drop_session.state == SessionState.ALLOW_CONTACT_REQUESTED.value:
            self.handle_drop_session_allow_contact_requested(message, drop_session)
            return

    def handle_no_active_airdrop_drop_session(self, customer, message, drop):
        if self.customer_has_completed_airdrop(customer, drop):
            self.messenger.log_and_send_message(customer, message.source,
                                 ("You've received your initial MOB, tried making a payment, "
                                  "and received a bonus! Well done. You've completed the MOB Coin Drop. "
                                  "Stay tuned for future drops."))
            return

        if not customer.phone_number.startswith(drop.number_restriction):
            self.messenger.log_and_send_message(customer, message.source,
                                 "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return

        customer_payments_address = self.payments.get_payments_address(message.source)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(customer, message.source,
                                 ("Hi! MOBot here.\n\nI'm a bot from MobileCoin that assists "
                                  "in making purchases using Signal Messenger and MobileCoin\n\n"
                                  "Uh oh! In-app payments are not enabled \n\n"
                                  f"Enable payments to receive {drop.item.description}\n\n"
                                  "More info on enabling payments here: "
                                  "https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments"))
            return

        if not self.under_drop_quota(drop):
            self.messenge.log_and_send_message(customer, message.source, "over quota for drop!")
            return

        if not self.minimum_coin_available(drop):
            self.messenger.log_and_send_message(customer, message.source, "no coin left!")
            return

        new_drop_session = DropSession(customer=customer, drop=drop, state=SessionState.READY_TO_RECEIVE_INITIAL.value)
        new_drop_session.save()

        self.messenger.log_and_send_message(customer, message.source,
                             ("Hi! MOBot here.\n\nWe're giving away free "
                              "MOB today so that you can try Signal's new payment feature!!!"))
        self.messenger.log_and_send_message(customer, message.source,
                             ("Here's how our MOB airdrop works:\n\n"
                              "1. We send you some MOB to fund your wallet. It will be approx £3 worth\n"
                              "2. Give sending MOB a try by giving us back a tiny bit, say 0.01 MOB\n"
                              "3. We'll send you a random BONUS airdrop. You could receive as much as £50 in MOB"
                              "\n\nWhether you get £5 or £50, it’s yours to keep and spend however you like"))
        self.messenger.log_and_send_message(customer, message.source, "Ready?")


