# Copyright (c) 2021 MobileCoin. All rights reserved.

import os
import full_service_cli as mc
import googlemaps
import enum

from mobot_client.drop_session import BaseDropSession, ItemSessionState
from mobot_client.models import (
    DropSession,
    CustomerStorePreferences,
    Order,
    Sku,
)
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

    @staticmethod
    def drop_item_has_stock_remaining(drop):
        # FIXME: Unused
        skus = Sku.objects.fliter(item=drop.item)
        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).count()
            if number_ordered < sku.quantity:
                return True

        return False

    def drop_item_get_available(self, drop_item):
        available_options = []
        skus = Sku.objects.filter(item=drop_item)

        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).count()
            if number_ordered < sku.quantity:
                available_options.append(sku)

        return available_options

    def handle_item_drop_session_waiting_for_size(self, message, drop_session):

        if message.text.lower() == "cancel" or message.text.lower() == 'refund':
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ITEM_OPTION_CANCEL
            )
            price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
            self.payments.send_mob_to_customer(drop_session.customer, message.source, price_in_mob, True)
            drop_session.state = ItemSessionState.REFUNDED.value
            drop_session.save()
            return
        elif message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ITEM_OPTION_HELP
            )
            return

        try:
            sku = Sku.objects.get(
                item=drop_session.drop.item, identifier__iexact=message.text
            )
        except (Exception,):
            message_to_send = f"{message.text} is not an available size"
            available_options = self.drop_item_get_available(drop_session.drop.item)
            message_to_send += "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE_OR_CANCEL

            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                message_to_send
            )
            return

        number_ordered = Order.objects.filter(sku=sku).count()
        if number_ordered >= sku.quantity:
            message_to_send = ChatStrings.ITEM_SOLD_OUT
            available_options = self.drop_item_get_available(drop_session.drop.item)
            message_to_send += "\n\n" + ChatStrings.get_options(available_options)
            message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, message_to_send
            )

            # price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
            # self.payments.send_mob_to_customer(drop_session.customer, message.source, price_in_mob, True)
            # drop_session.state = ItemSessionState.REFUNDED.value
            # drop_session.save()
            return

        new_order = Order(
            customer=drop_session.customer, drop_session=drop_session, sku=sku
        )
        new_order.save()

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.ADDRESS_HOODIE_REQUEST
        )

        drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS.value
        drop_session.save()

    def handle_item_drop_session_waiting_for_payment(self, message, drop_session):
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ITEM_HELP
            )

        elif message.text.lower() == "cancel":
            drop_session.state = ItemSessionState.CANCELLED.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.SESSION_CANCELLED
            )
            return

        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PAY.format(amount=price_in_mob.normalize()),
            )

        elif message.text.lower() == "terms":
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.TERMS
            )
        elif message.text.lower() == "info":
            drop_item = drop_session.drop.item

            item_description_text = drop_item.name

            if drop_item.description is not None:
                item_description_text = drop_item.description
            elif drop_item.short_description is not None:
                item_description_text = drop_item.short_description

            if drop_item.image_link is None or drop_item.image_link == "":
                self.messenger.log_and_send_message(
                    drop_session.customer, message.source, item_description_text
                )
            else:
                attachments = [
                    "/signald/attachments/" + attachment.strip()
                    for attachment in drop_item.image_link.split(",")
                ]
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    message.source,
                    item_description_text,
                    attachments=attachments,
                )
        else:
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ITEM_HELP_SHORT
            )

        # Re-display available sizes and request payment
        drop_item = drop_session.drop.item
        available_options = self.drop_item_get_available(drop_item)
        if len(available_options) == 0:
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.OUT_OF_STOCK
            )
            drop_session.state = ItemSessionState.CANCELLED.value
            drop_session.save()
            return

        message_to_send = f"{drop_item.name} in " + ChatStrings.get_options(available_options)        
        price_in_mob = mc.pmob2mob(drop_item.price_in_pmob)
        message_to_send += "\n\n" + ChatStrings.PAYMENT_REQUEST.format(price=price_in_mob.normalize())
        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            message_to_send
        )

    def handle_item_drop_session_waiting_for_address(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except (Exception,):
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )

            return

        address = self.gmaps.geocode(message.text)

        if len(address) == 0:
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ADDRESS_NOT_FOUND
            )

            return

        order.shipping_address = address[0]["formatted_address"]
        order.save()

        drop_session.state = ItemSessionState.WAITING_FOR_NAME.value
        drop_session.save()

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.NAME_REQUEST
        )

    def handle_item_drop_session_waiting_for_name(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except (Exception,):
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )
            return

        order.shipping_name = message.text
        order.save()

        drop_session.state = ItemSessionState.SHIPPING_INFO_CONFIRMATION.value
        drop_session.save()

        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.VERIFY_SHIPPING.format(
                name=order.shipping_name, address=order.shipping_address
            ),
        )

    def handle_item_drop_session_shipping_confirmation(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except (Exception,):
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )
            return

        if message.text.lower() == "no" or message.text.lower() == "n":
            drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ADDRESS_REQUEST
            )

            return

        order.status = OrderStatus.CONFIRMED.value
        order.save()

        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.ORDER_CONFIRMATION.format(
                order_id=order.id, sku_name=order.sku.item.name
            ),
        )

        if message.text.lower() == "yes" or message.text.lower() == "y":
            if self.customer_has_store_preferences(drop_session.customer):
                drop_session.state = ItemSessionState.COMPLETED.value
                drop_session.save()
                self.messenger.log_and_send_message(
                    drop_session.customer, message.source, ChatStrings.BYE
                )

                return

            drop_session.state = ItemSessionState.ALLOW_CONTACT_REQUESTED.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.FUTURE_NOTIFICATIONS
            )

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.NOTIFICATIONS_HELP
        )

    def handle_item_drop_session_allow_contact_requested(self, message, drop_session):
        if message.text.lower() == "n" or message.text.lower() == "no":
            customer_store_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=False
            )
            customer_store_prefs.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.BYE
            )
            drop_session.state = ItemSessionState.COMPLETED.value
            drop_session.save()
            return

        if message.text.lower() == "y" or message.text.lower() == "yes":
            customer_store_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=True
            )
            customer_store_prefs.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.BYE
            )
            drop_session.state = ItemSessionState.COMPLETED.value
            drop_session.save()
            return

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.NOTIFICATIONS_HELP_ALT
        )

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
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.COUNTRY_RESTRICTED
            )
            return

        customer_payments_address = self.payments.get_payments_address(message.source)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.PAYMENTS_ENABLED_HELP.format(
                    item_desc=drop.item.description
                ),
            )
            return

        # Greet the user
        message_to_send = ChatStrings.ITEM_DROP_GREETING.format(
            store_name=drop.store.name,
            store_description=drop.store.description,
            item_description=drop.item.description
        )
        # self.messenger.log_and_send_message(
        #     customer,
        #     message.source,
        #     message_to_send
        # )

        available_options = self.drop_item_get_available(drop.item)
        if len(available_options) == 0:
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.OUT_OF_STOCK
            )
            return

        message_to_send += "\n\n"+ChatStrings.get_options(available_options, capitalize=True)

        price_in_mob = mc.pmob2mob(drop.item.price_in_pmob)
        message_to_send += "\n\n"+ChatStrings.ITEM_DISCOUNT.format(
            price=price_in_mob.normalize()
        )

        self.messenger.log_and_send_message(customer, message.source, message_to_send)
        self.messenger.log_and_send_message(
            customer,
            message.source,
            ChatStrings.PAYMENT_REQUEST.format(price=price_in_mob.normalize()),
        )

        new_drop_session, _ = DropSession.objects.get_or_create(
            customer=customer,
            drop=drop,
            state=ItemSessionState.WAITING_FOR_PAYMENT.value,
        )
