# Copyright (c) 2021 MobileCoin. All rights reserved.

import os
import full_service_cli as mc
import googlemaps
import enum

from mobot_client.drop_session import BaseDropSession, ItemSessionState
from mobot_client.models import Customer, DropSession, CustomerStorePreferences, BonusCoin, Order, Sku
from mobot_client.chat_strings import ChatStrings


class OrderStatus(enum.Enum):
    STARTED = 0
    CONFIRMED = 1
    SHIPPED = 2


class ItemDropSession(BaseDropSession):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        gmaps_client_key = os.environ["GMAPS_CLIENT_KEY"]
        self.gmaps = googlemaps.Client(key=gmaps_client_key)

    def handle_item_drop_session_waiting_for_size(self, message, drop_session):
        try:
            sku = Sku.objects.get(item=drop_session.drop.item, identifier__iexact=message.text)
        except:
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                f"No option found for {message.text}")
            return

        number_ordered = Order.objects.filter(sku=sku).count()
        if number_ordered >= sku.quantity:
            self.messenger.log_and_send_message(drop_session.customer, message.source, ChatStrings.ITEM_SOLD_OUT)

            price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
            self.payments.send_mob_to_customer(message.source, price_in_mob, True)
            drop_session.state = ItemSessionState.REFUNDED.value
            drop_session.save()
            return

        new_order = Order(customer=drop_session.customer, drop_session=drop_session, sku=sku)
        new_order.save()

        self.messenger.log_and_send_message(drop_session.customer, message.source, ChatStrings.ADDRESS_REQUEST)

        drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS
        drop_session.save()

    def handle_item_drop_session_waiting_for_payment(self, message, drop_session):
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.ITEM_HELP)

        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PAY.format(amount=price_in_mob.normalize()))

        elif message.text.lower() == "terms":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.TERMS)
        elif message.text.lower() == "info":
            drop_item = drop_session.drop.item

            item_description_text = drop_item.name

            if drop_item.description is not None:
                item_description_text = drop_item.description
            elif drop_item.short_description is not None:
                item_description_text = drop_item.short_description

            if drop_item.image_link is None or drop_item.image_link == "":
                self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                    item_description_text)
            else:
                attachments = ['/signald/attachments/' + attachment.strip() for attachment in
                               drop_item.image_link.split(',')]
                self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                    item_description_text, attachments=attachments)
        else:
            self.messenger.log_and_send_message(drop_session.customer,
                                                message.source,
                                                ChatStrings.ITEM_HELP_SHORT)

        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
        self.messenger.log_and_send_message(drop_session.customer, message.source, ChatStrings.RESERVE_ITEM.format(amount=price_in_mob.normalize()))

    def handle_item_drop_session_waiting_for_address(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except:
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "We don't seem to have an order for you... something went wrong! Please try again")
            return

        address = self.gmaps.geocode(message.text)

        if len(address) == 0:
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "We couldn't seem to find that address. Please try again!")
            return

        order.shipping_address = address[0]['formatted_address']
        order.save()

        drop_session.state = ItemSessionState.WAITING_FOR_NAME.value
        drop_session.save()

        self.messenger.log_and_send_message(drop_session.customer, message.source,
                                            "What name should we use to send the order to?")

    def handle_item_drop_session_waiting_for_name(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except:
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "We don't seem to have an order for you... something went wrong! Please try again")
            return

        order.shipping_name = message.text
        order.save()

        drop_session.state = ItemSessionState.SHIPPING_INFO_CONFIRMATION.value
        drop_session.save()

        self.messenger.log_and_send_message(drop_session.customer, message.source,
                                            f"Does this look correct?\n{order.shipping_name}\n{order.shipping_address}")

    def handle_item_drop_session_shipping_confirmation(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except:
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "We don't seem to have an order for you... something went wrong! Please try again")
            return

        if message.text.lower() == "no" or message.text.lower() == "n":
            drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS.value
            drop_session.save()
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "What address should we ship to?")
            return

        order.status = OrderStatus.CONFIRMED.value
        order.save()

        self.messenger.log_and_send_message(drop_session.customer, message.source,
                                            (f"All set. Your order number is {order.id}\n\n"
                                             f"1x {order.sku.item.name}, to be shipped to you\n\n"
                                             f"Please provide your order number ({order.id}) when contacting us "
                                             "if you have any questions or issues"))

        if message.text.lower() == "yes" or message.text.lower() == "y":
            if self.customer_has_store_preferences(drop_session.customer):
                drop_session.state = ItemSessionState.COMPLETED.value
                drop_session.save()
                self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                    "Thanks! MOBot out, buh-bye!")
                return

            drop_session.state = ItemSessionState.ALLOW_CONTACT_REQUESTED.value
            drop_session.save()
            self.messenger.log_and_send_message(drop_session.customer, message.source,
                                                "Can we contact you for future drops?")

        self.messenger.log_and_send_message(drop_session.customer, message.source, "Valid commands are y(es) and n(o)")

    def handle_item_drop_session_allow_contact_requested(self, message, drop_session):
        if message.text.lower() == "n" or message.text.lower() == "no":
            customer_store_prefs = CustomerStorePreferences(customer=drop_session.customer, store=self.store,
                                                            allows_contact=False)
            customer_store_prefs.save()
            self.messenger.log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye!")
            drop_session.state = ItemSessionState.COMPLETED
            drop_session.save()
            return

        if message.text.lower() == "y" or message.text.lower() == "yes":
            customer_store_prefs = CustomerStorePreferences(customer=drop_session.customer, store=self.store,
                                                            allows_contact=True)
            customer_store_prefs.save()
            self.messenger.log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye!")
            drop_session.state = ItemSessionState.COMPLETED
            drop_session.save()
            return

        self.messenger.log_and_send_message(drop_session.customer, message.source,
                                            "You can type (y)es or (n)o\n\nWould you like to receive an alert when we are doing future drops?")

    def handle_active_item_drop_session(self, message, drop_session):
        print(drop_session.state)
        if drop_session.state == ItemSessionState.WAITING_FOR_PAYMENT.value:
            self.handle_item_drop_session_waiting_for_payment(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_SIZE.value:
            self.handle_item_drop_session_waiting_for_size(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_ADDRESS.value:
            self.handle_item_drop_session_waiting_for_address(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_NAME.value:
            self.handle_item_drop_session_waiting_for_name(message, drop_session)
            return

        if drop_session.state == ItemSessionState.SHIPPING_INFO_CONFIRMATION.value:
            self.handle_item_drop_session_shipping_confirmation(message, drop_session)
            return

        if drop_session.state == ItemSessionState.ALLOW_CONTACT_REQUESTED.value:
            self.handle_item_drop_session_allow_contact_requested(message, drop_session)
            return

    def handle_no_active_item_drop_session(self, customer, message, drop):
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

        available_options = []
        skus = Sku.objects.filter(item=drop.item)

        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).count()
            if number_ordered < sku.quantity:
                available_options.append(sku)

        if len(available_options) == 0:
            self.messenger.log_and_send_message(customer, message.source,
                                                f"Uh oh! Looks like we're all out of stock, sorry!")
            return

        message_to_send = "We have the following available options:\n\n"
        for option in available_options:
            message_to_send += f" - {option.identifier}\n"

        self.messenger.log_and_send_message(customer, message.source, message_to_send)
        price_in_mob = mc.pmob2mob(drop.item.price_in_pmob)
        self.messenger.log_and_send_message(customer, message.source,
                                            f"Send {price_in_mob.normalize()} MOB to reserve your item now!")

        new_drop_session, _ = DropSession.objects.get_or_create(customer=customer, drop=drop,
                                                                state=ItemSessionState.WAITING_FOR_PAYMENT.value)
