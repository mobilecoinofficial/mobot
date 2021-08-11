# Copyright (c) 2021 MobileCoin. All rights reserved.

import os
import mobilecoin as mc
import googlemaps
import enum
import pytz

from mobot_client.drop_session import BaseDropSession, ItemSessionState
from mobot_client.models import (
    DropSession,
    CustomerStorePreferences,
    Order,
    Sku,
    CustomerDropRefunds,
)
from mobot_client.chat_strings import ChatStrings


class OrderStatus(enum.Enum):
    STARTED = 0
    CONFIRMED = 1
    SHIPPED = 2
    CANCELLED = 3


class ItemDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        gmaps_client_key = os.environ["GMAPS_CLIENT_KEY"]
        self.gmaps = googlemaps.Client(key=gmaps_client_key)
        
        self.vat_id = os.environ["VAT_ID"]

    @staticmethod
    def drop_item_has_stock_remaining(drop):
        # FIXME: Unused
        skus = Sku.objects.fliter(item=drop.item)
        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED.value).count()
            if number_ordered < sku.quantity:
                return True

        return False

    def drop_item_get_available(self, drop_item):
        available_options = []
        skus = Sku.objects.filter(item=drop_item).order_by("sort_order")

        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED.value).count()
            if number_ordered < sku.quantity:
                available_options.append(sku)

        return available_options

    def handle_item_drop_session_waiting_for_size(self, message, drop_session):

        if message.text.lower() == "cancel" or message.text.lower() == 'refund':
            self.handle_cancel_and_refund(message, drop_session, None)
            return
        elif message.text.lower() == "help" or message.text == '?':
            available_options = self.drop_item_get_available(drop_session.drop.item)
            self.messenger.log_and_send_message(
                drop_session.customer, message.source,
                ChatStrings.ITEM_OPTION_HELP + "\n\n" + ChatStrings.get_options(available_options,capitalize=True) 
            )
            return

        elif message.text.lower() == "privacy":
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )

            available_options = self.drop_item_get_available(drop_session.drop.item)
            message_to_send = "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE_OR_CANCEL

            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                message_to_send
            )
            return

        elif message.text.lower() == "chart" or message.text.lower() == 'info':
            drop_item = drop_session.drop.item

            item_description_text = drop_item.name

            if drop_item.short_description is not None:
                item_description_text = drop_item.short_description

            if drop_item.image_link is None or drop_item.image_link == "":
                self.messenger.log_and_send_message(
                    drop_session.customer, message.source,
                    ChatStrings.ITEM_OPTION_NO_CHART.format(description=drop_item.short_description)
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

            available_options = self.drop_item_get_available(drop_session.drop.item)
            message_to_send = "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE_OR_CANCEL

            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                message_to_send
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

        number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED.value).count()
        if number_ordered >= sku.quantity:
            message_to_send = ChatStrings.ITEM_SOLD_OUT
            available_options = self.drop_item_get_available(drop_session.drop.item)
            message_to_send += "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, message_to_send
            )

            return

        new_order = Order(
            customer=drop_session.customer,
            drop_session=drop_session,
            sku=sku,
            conversion_rate_mob_to_currency=drop_session.drop.conversion_rate_mob_to_currency
        )
        new_order.save()

        drop_session.state = ItemSessionState.WAITING_FOR_NAME.value
        drop_session.save()

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.NAME_REQUEST
        )

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

        # elif message.text.lower() == "terms":
        #     self.messenger.log_and_send_message(
        #         drop_session.customer, message.source, ChatStrings.TERMS
        #     )

        elif message.text.lower() == "privacy":
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )

        elif message.text.lower() == "info":
            drop_item = drop_session.drop.item

            item_description_text = drop_item.description or drop_item.short_description or drop_item.name

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
                drop_session.customer, message.source, ChatStrings.OUT_OF_STOCK
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

    def handle_cancel_and_refund(self, message, drop_session, order):
        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.ITEM_OPTION_CANCEL
        )
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

        customer_drop_refunds, _ = CustomerDropRefunds.objects.get_or_create(customer=drop_session.customer, drop=drop_session.drop)
        
        should_refund_transaction_fee = False

        if customer_drop_refunds.number_of_times_refunded < drop_session.drop.max_refund_transaction_fees_covered:
            should_refund_transaction_fee = True
            customer_drop_refunds.number_of_times_refunded = customer_drop_refunds.number_of_times_refunded + 1
            customer_drop_refunds.save()

        self.payments.send_mob_to_customer(drop_session.customer, message.source, price_in_mob, should_refund_transaction_fee)
        
        if order is not None:
            order.status = OrderStatus.CANCELLED.value
            order.save()

        drop_session.state = ItemSessionState.REFUNDED.value
        drop_session.save()

    def handle_item_drop_session_waiting_for_address(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except (Exception,):
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )

            return

        address = self.gmaps.geocode(message.text, region=drop_session.drop.country_code_restriction)

        if len(address) == 0:
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.ADDRESS_NOT_FOUND
            )

            return

        if message.text == "?" or message.text.lower() == 'help':
            self.messenger.log_and_send_message(
                drop_session.customer, message.source,
                ChatStrings.ADDRESS_HELP.format(item=drop_session.drop.item.name)
            )
            return

        if message.text.lower() == "cancel":
            self.handle_cancel_and_refund(message, drop_session, order)
            return

        address_components = address[0]["address_components"]
        for component in address_components:
            types = component["types"]
            for type in types:
                if type == "country" and component["short_name"] != drop_session.drop.country_code_restriction:
                    self.messenger.log_and_send_message(
                        drop_session.customer, message.source, ChatStrings.ADDRESS_RESTRICTION.format(country=drop_session.drop.country_long_name_restriction)
                    )
                    return

        order.shipping_address = address[0]["formatted_address"]
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

    def handle_item_drop_session_waiting_for_name(self, message, drop_session):
        order = None
        try:
            order = Order.objects.get(drop_session=drop_session)
        except (Exception,):
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )
            return

        if message.text == "?" or message.text.lower() == 'help':
            self.messenger.log_and_send_message(
                drop_session.customer, message.source,
                ChatStrings.NAME_HELP
            )
            return

        if message.text.lower() == "cancel":
            self.handle_cancel_and_refund(message, drop_session, order)
            return

        order.shipping_name = message.text
        order.save()

        drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS.value
        drop_session.save()
        
        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.ADDRESS_REQUEST
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
            drop_session.state = ItemSessionState.WAITING_FOR_NAME.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.NAME_REQUEST
            )
            return

        if message.text.lower() == "privacy":
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )

        if message.text.lower() == "c" or message.text.lower() == "cancel" or message.text.lower() == "refund":
            self.handle_cancel_and_refund(message, drop_session, order)
            return

        if message.text.lower() != "yes" and message.text.lower() != "y":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.SHIPPING_CONFIRMATION_HELP.format(
                    name=order.shipping_name, address=order.shipping_address
                )
            )
            return

        order.status = OrderStatus.CONFIRMED.value
        order.save()

        item = drop_session.drop.item
        price_in_mob = mc.pmob2mob(item.price_in_pmob)
        price_local_fiat = float(price_in_mob) * drop_session.drop.conversion_rate_mob_to_currency
        vat = price_local_fiat * 1/6
        tz = pytz.timezone(drop_session.drop.timezone)
        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.ORDER_CONFIRMATION.format(
                order_id=order.id,
                today=order.date.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z"),
                item_name = item.name,
                sku_name=order.sku.identifier,
                price=price_in_mob.normalize(),
                ship_name=order.shipping_name,
                ship_address=order.shipping_address,
                vat=vat,
                vat_id=self.vat_id,
                store_name=drop_session.drop.store.name,
                store_contact="hello@mobilecoin.com"
            ),
        )

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

        if message.text.lower() == 'p' or message.text.lower() == "privacy" or message.text.lower() == "privacy policy":
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY_REPROMPT.format(url=privacy_policy_url),
            )
            return

        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.HELP
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
                    item_desc=drop.item.short_description
                ),
            )
            return

        # Greet the user
        message_to_send = ChatStrings.ITEM_DROP_GREETING.format(
            store_name=drop.store.name,
            store_description=drop.store.description,
            item_description=drop.item.short_description
        )

        available_options = self.drop_item_get_available(drop.item)
        if len(available_options) == 0:
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.OUT_OF_STOCK
            )
            return

        message_to_send += "\n\n"+ChatStrings.get_options(available_options, capitalize=True)

        price_in_mob = mc.pmob2mob(drop.item.price_in_pmob)
        message_to_send += "\n\n"+ChatStrings.ITEM_DISCOUNT.format(
            price=price_in_mob.normalize(),
            country=drop.country_long_name_restriction
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
