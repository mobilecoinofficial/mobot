# Copyright (c) 2021 MobileCoin. All rights reserved.

from decimal import Decimal

import googlemaps
import pytz

from django.conf import settings

from mobot_client.core.context import ChatContext
from mobot_client.drop_session import BaseDropSession
from mobot_client.models import (
    DropSession,
    Drop,
    CustomerStorePreferences,
    Order,
    Sku,
    CustomerDropRefunds, SessionState, OrderStatus,
    OutOfStockException,
)
from mobot_client.chat_strings import ChatStrings
from mobot_client.models.messages import Message


class ItemDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gmaps = googlemaps.Client(key=settings.GMAPS_CLIENT_KEY)
        self.vat_id = settings.VAT_ID

    def handle_active_item_drop_session(self, message, drop_session):
        if drop_session.state == SessionState.WAITING_FOR_PAYMENT:
            self.handle_item_drop_session_waiting_for_payment(message, drop_session)
        elif drop_session.state == SessionState.WAITING_FOR_SIZE:
            self.handle_item_drop_session_waiting_for_size(message, drop_session)
        elif drop_session.state == SessionState.WAITING_FOR_ADDRESS:
            self.handle_item_drop_session_waiting_for_address(message, drop_session)
        elif drop_session.state == SessionState.WAITING_FOR_NAME:
            self.handle_item_drop_session_waiting_for_name(message, drop_session)
        elif drop_session.state == SessionState.SHIPPING_INFO_CONFIRMATION:
            self.handle_item_drop_session_shipping_confirmation(message, drop_session)
        elif drop_session.state == SessionState.ALLOW_CONTACT_REQUESTED:
            self.handle_item_drop_session_allow_contact_requested(drop_session)
        elif drop_session.state == SessionState.READY:
            self.show_catalog_and_display_payment_instructions(drop_session)

    def handle_item_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        payment_succeeded = self.payments.handle_item_payment(amount_paid_mob, drop_session)
        if payment_succeeded:
            message_to_send = (
                ChatStrings.WAITING_FOR_SIZE_PREFIX + ChatStrings.get_options(list(drop_session.drop.item.skus.all()), capitalize=True)
            )
            self.messenger.log_and_send_message(message_to_send)
            drop_session.state = SessionState.WAITING_FOR_SIZE
        drop_session.save()

    def handle_item_drop_session_waiting_for_size(self, message, drop_session):
        if message.text.lower() == "cancel" or message.text.lower() == 'refund':
            self.handle_cancel_and_refund(message, drop_session, None)
        elif message.text.lower() == "help" or message.text == '?':
            self.messenger.log_and_send_message(
                ChatStrings.ITEM_OPTION_HELP + "\n\n" + ChatStrings.get_options(drop_session.drop.item.skus, capitalize=True)
            )
        elif message.text.lower() == "privacy":
            self.handle_privacy_policy_request(drop_session)
            self.show_catalog(message, drop_session)
        elif message.text.lower() == "chart" or message.text.lower() == 'info':
            drop_item = drop_session.drop.item

            item_description_text = drop_item.name

            if drop_item.short_description is not None:
                item_description_text = drop_item.short_description

            if drop_item.image_link is None or drop_item.image_link == "":
                self.messenger.log_and_send_message(
                    ChatStrings.ITEM_OPTION_NO_CHART.format(description=drop_item.short_description)
                )
            else:
                attachments = [
                    "/signald/attachments/" + attachment.strip()
                    for attachment in drop_item.image_link.split(",")
                ]
                self.messenger.log_and_send_message(
                    item_description_text,
                    attachments=attachments,
                )
            self.show_catalog(message, drop_session)
        else:
            sku: Sku = drop_session.drop.item.skus.filter(identifier__iexact=message.text).first()
            if not sku:
                message_to_send = f"{message.text} is not an available size"
                self.show_catalog(drop_session, message_to_send)
            else:
                try:
                    # Atomically order the item
                    order = sku.order(drop_session)
                    self.logger.info(f"Successfully created order: {order}")
                except OutOfStockException:
                    self.show_catalog(drop_session, ChatStrings.ITEM_SOLD_OUT)
                else:
                    drop_session.state = SessionState.WAITING_FOR_NAME
                    drop_session.save()

                    self.messenger.log_and_send_message(
                        ChatStrings.NAME_REQUEST
                    )

    def handle_item_drop_session_waiting_for_payment(self, message: Message, drop_session: DropSession):
        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                ChatStrings.ITEM_HELP
            )
        elif message.text.lower() == "cancel":
            self.handle_cancel(drop_session)
        elif message.text.lower() == "pay":
            self.messenger.log_and_send_message(
                ChatStrings.PAY.format(amount=drop_session.drop.item.price_in_mob.normalize()),
            )
        elif message.text.lower() == "privacy":
            self.handle_privacy_policy_request(drop_session)
        elif message.text.lower() == "info":
            drop_item = drop_session.drop.item

            item_description_text = drop_item.description or drop_item.short_description or drop_item.name

            if drop_item.image_link is None or drop_item.image_link == "":
                self.messenger.log_and_send_message(
                    item_description_text
                )
            else:
                attachments = [
                    "/signald/attachments/" + attachment.strip()
                    for attachment in drop_item.image_link.split(",")
                ]
                self.messenger.log_and_send_message(
                    item_description_text,
                    attachments=attachments,
                )
        else:
            self.messenger.log_and_send_message(
                ChatStrings.ITEM_HELP_SHORT
            )
        # Re-display available sizes and request payment
        self.show_catalog_and_display_payment_instructions(drop_session)
        drop_session.save()

    def handle_cancel_and_refund(self, message, drop_session, order):
        self.messenger.log_and_send_message(
            ChatStrings.ITEM_OPTION_CANCEL
        )
        customer_drop_refunds, _ = CustomerDropRefunds.objects.get_or_create(customer=drop_session.customer, drop=drop_session.drop)

        if should_refund_transaction_fee := customer_drop_refunds.number_of_times_refunded < drop_session.drop.max_refund_transaction_fees_covered:
            customer_drop_refunds.number_of_times_refunded = customer_drop_refunds.number_of_times_refunded + 1
            customer_drop_refunds.save()

        self.payments.send_reply_payment(drop_session.drop.item.price_in_mob, should_refund_transaction_fee)
        
        if order is not None:
            order.status = OrderStatus.CANCELLED
            order.save()

        drop_session.state = SessionState.REFUNDED
        drop_session.save()

    def validate_address(self, address, drop_session: DropSession) -> bool:
        address_components = address[0]["address_components"]
        for component in address_components:
            types = component["types"]
            for TYPE in types:
                if TYPE == "country" and component["short_name"] != drop_session.drop.country_code_restriction:
                    return False

    def validated_address(self, drop_session: DropSession):
        ctx = ChatContext.get_current_context()
        message = ctx.message
        address = self.gmaps.geocode(message.text, region=drop_session.drop.country_code_restriction)
        order = drop_session.order
        if len(address) == 0:
            self.messenger.log_and_send_message(
                ChatStrings.ADDRESS_NOT_FOUND
            )
        elif message.text == "?" or message.text.lower() == 'help':
            self.messenger.log_and_send_message(
                ChatStrings.ADDRESS_HELP.format(item=drop_session.drop.item.name)
            )
        elif message.text.lower() == "cancel":
            self.handle_cancel_and_refund(message, drop_session, order)
        elif self.validate_address(address, drop_session):
            return address

    def handle_item_drop_session_waiting_for_address(self, message, drop_session):
        order = Order.objects.filter(drop_session=drop_session).first()
        if not order:
            self.messenger.log_and_send_message(
                ChatStrings.MISSING_ORDER
            )
        elif address := self.validated_address(drop_session):
            order.shipping_address = address[0]["formatted_address"]
            order.save()

            drop_session.state = SessionState.SHIPPING_INFO_CONFIRMATION

            self.messenger.log_and_send_message(
                ChatStrings.VERIFY_SHIPPING.format(
                    name=order.shipping_name, address=order.shipping_address
                ),
            )
        else:
            self.messenger.log_and_send_message(
                ChatStrings.ADDRESS_RESTRICTION.format(
                    drop_session.drop.country_code_restriction
                )
            )
            drop_session.state = SessionState.CUSTOMER_DOES_NOT_MEET_RESTRICTIONS
        drop_session.save()

    def handle_item_drop_session_waiting_for_name(self, message, drop_session):
        order = drop_session.order
        if message.text == "?" or message.text.lower() == 'help':
            self.messenger.log_and_send_message(
                ChatStrings.NAME_HELP
            )
        elif message.text.lower() == "cancel":
            self.handle_cancel_and_refund(message, drop_session, order)
        else:
            order.shipping_name = message.text
            order.save()

            drop_session.state = SessionState.WAITING_FOR_ADDRESS
            drop_session.save()

            self.messenger.log_and_send_message(
                ChatStrings.ADDRESS_REQUEST
            )

    def confirm_order(self, drop_session: DropSession):
        order = drop_session.order
        order.status = OrderStatus.CONFIRMED
        order.save()

        item = drop_session.drop.item
        price_local_fiat = float(item.price_in_mob) * drop_session.drop.conversion_rate_mob_to_currency
        vat = price_local_fiat * 1 / 6
        tz = pytz.timezone(drop_session.drop.timezone)
        self.messenger.log_and_send_message(
            ChatStrings.ORDER_CONFIRMATION.format(
                order_id=order.id,
                today=order.date.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z"),
                item_name=item.name,
                sku_name=order.sku.identifier,
                price=item.price_in_mob.normalize(),
                ship_name=order.shipping_name,
                ship_address=order.shipping_address,
                vat=vat,
                vat_id=self.vat_id,
                store_name=drop_session.drop.store.name,
                store_contact="hello@mobilecoin.com"
            ),
        )

    def handle_item_drop_session_shipping_confirmation(self, message: Message, drop_session: DropSession):
        if not drop_session.order:
            self.messenger.log_and_send_message(
                ChatStrings.MISSING_ORDER
            )
        elif message.text.lower() == "no" or message.text.lower() == "n":
            drop_session.state = SessionState.WAITING_FOR_NAME
            drop_session.save()
            self.messenger.log_and_send_message(
                ChatStrings.NAME_REQUEST
            )
        elif message.text.lower() == "privacy":
            self.handle_privacy_policy_request(drop_session)
        elif message.text.lower() == "c" or message.text.lower() == "cancel" or message.text.lower() == "refund":
            self.handle_cancel_and_refund(message, drop_session, drop_session.order)
        elif message.text.lower() != "yes" and message.text.lower() != "y":
            self.messenger.log_and_send_message(
                ChatStrings.SHIPPING_CONFIRMATION_HELP.format(
                    name=drop_session.order.shipping_name, address=drop_session.order.shipping_address
                )
            )
        else:
            self.confirm_order(drop_session)
        # Finish off by offering further contact
        self.handle_item_drop_session_allow_contact_requested(drop_session)

    def handle_item_drop_session_allow_contact_requested(self, drop_session: DropSession):
        message = ChatContext.get_current_context().message
        if message.text.lower() == "n" or message.text.lower() == "no":
            customer_store_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=False
            )
            customer_store_prefs.save()
            self.messenger.log_and_send_message(
                ChatStrings.BYE
            )
            drop_session.state = SessionState.COMPLETED
        elif message.text.lower() == "y" or message.text.lower() == "yes":
            customer_store_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=True
            )
            customer_store_prefs.save()
            self.messenger.log_and_send_message(
                ChatStrings.BYE
            )
            drop_session.state = SessionState.COMPLETED
        elif message.text.lower() == 'p' or message.text.lower() == "privacy" or message.text.lower() == "privacy policy":
            self.handle_privacy_policy_request(drop_session)
        else:
            self.messenger.log_and_send_message(
                ChatStrings.HELP
            )
        drop_session.save()

    def request_payment_from_customer(self, drop_session: DropSession, price_in_mob: Decimal):
        self.messenger.log_and_send_message(
            ChatStrings.PAYMENT_REQUEST.format(price=price_in_mob.normalize()),
        )
        drop_session.state = SessionState.WAITING_FOR_PAYMENT

    def show_catalog(self, drop_session: DropSession, message_to_send: str = ""):
        drop = drop_session.drop
        available_options = drop.item.skus.all()
        if not available_options.exists():
            self.messenger.log_and_send_message(
                ChatStrings.OUT_OF_STOCK
            )
            drop_session.state = SessionState.OUT_OF_STOCK
        else:
            message_to_send += "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            price_in_mob = drop.item.price_in_mob
            message_to_send += "\n\n" + ChatStrings.ITEM_DISCOUNT.format(
                price=price_in_mob.normalize(),
                country=drop.country_long_name_restriction
            )
            self.messenger.log_and_send_message(message_to_send)

    def show_catalog_and_display_payment_instructions(self, drop_session: DropSession):
        ctx = ChatContext.get_current_context()
        drop = drop_session.drop
        customer_payments_address = self.payments.get_payments_address(ctx.customer.phone_number.as_e164)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(
                ChatStrings.PAYMENTS_ENABLED_HELP.format(
                    item_desc=drop.item.short_description
                ),
            )
        else:
            # Greet the user
            greeting_text = ChatStrings.ITEM_DROP_GREETING.format(
                store_name=drop.store.name,
                store_description=drop.store.description,
                item_description=drop.item.short_description
            )
            self.show_catalog(drop_session, greeting_text)
            self.request_payment_from_customer(drop_session, drop_session.drop.item.price_in_mob)
            drop_session.save()

    def handle_no_active_item_drop_session(self, drop: Drop):
        ctx = ChatContext.get_current_context()
        customer = ctx.customer
        new_drop_session, _ = DropSession.objects.get_or_create(
            customer=customer,
            drop=drop,
            state=SessionState.READY,
        )
        if not customer.matches_country_code_restriction(drop):
            self.messenger.log_and_send_message(
                ChatStrings.COUNTRY_RESTRICTED
            )
            new_drop_session.state = SessionState.CUSTOMER_DOES_NOT_MEET_RESTRICTIONS
        else:
            self.show_catalog_and_display_payment_instructions(new_drop_session)
