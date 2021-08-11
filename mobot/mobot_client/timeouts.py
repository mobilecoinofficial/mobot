# Copyright (c) 2021 MobileCoin. All rights reserved.

import datetime
import pytz
import time

import mobilecoin as mc

from mobot_client.models import DropSession, Customer, Message
from mobot_client.drop_session import ItemSessionState
from mobot_client.chat_strings import ChatStrings

utc = pytz.UTC


class Timeouts:

    def __init__(self, messenger, payments, schedule=30, idle_timeout=60, cancel_timeout=300):
        self.messenger = messenger
        self.schedule = schedule
        self.payments = payments

        # Time before warning
        self.idle_timeout = idle_timeout

        # Time before cancelling session and refunding payment
        self.cancel_timeout = cancel_timeout

    @staticmethod
    def customer_is_active(customer):
        session = DropSession.objects.filter(customer=customer).values('state').last()
        if session is not None and session['state'] in ItemSessionState.active_states():
            return True
        return False

    @staticmethod
    def customer_is_idle(customer):
        session = DropSession.objects.filter(customer=customer).values('state').last()
        if session is not None and (session['state'] == ItemSessionState.IDLE.value or session['state'] == ItemSessionState.IDLE_AND_REFUNDABLE.value):
            return True
        return False

    @staticmethod
    def customer_needs_refund(customer):
        session = DropSession.objects.filter(customer=customer).values('state').last()
        if session is not None and session['state'] in ItemSessionState.refundable_states():
            return True
        return False

    @staticmethod
    def set_customer_idle(customer):
        session = DropSession.objects.filter(customer=customer).last()
        if session is not None and session.state in ItemSessionState.active_states():
            session.state = ItemSessionState.IDLE.value
            session.save()

    @staticmethod
    def set_customer_idle(customer):
        session = DropSession.objects.filter(customer=customer).last()
        if session is not None and session.state in ItemSessionState.active_states():
            if session.state in ItemSessionState.refundable_states():
                session.state = ItemSessionState.IDLE_AND_REFUNDABLE.value
            else:
                session.state = ItemSessionState.IDLE.value
            session.save()

    @staticmethod
    def set_customer_refunded(customer):
        session = DropSession.objects.filter(customer=customer).last()
        if session is not None and (session.state in ItemSessionState.active_states() or session.state == ItemSessionState.IDLE.value):
            session.state = ItemSessionState.REFUNDED.value
            session.save()

    @staticmethod
    def set_customer_cancelled(customer):
        session = DropSession.objects.filter(customer=customer).last()
        if session is not None and (session.state in ItemSessionState.active_states() or session.state == ItemSessionState.IDLE.value):
            session.state = ItemSessionState.CANCELLED.value
            session.save()

    def do_refund(self, customer):
        session = DropSession.objects.filter(customer_id=customer.phone_number).last()
        if session is None:
            return
        # Confirm drop session is active
        # FIXME TODO

        # Get amount customer paid
        price = session.drop.item.price_in_pmob

        self.payments.send_mob_to_customer(customer, customer.phone_number, mc.pmob2mob(price), True)
        self.set_customer_refunded(customer)

    # FIXME: might need to not be a class method in order to get discovered
    def process_timeouts(self):
        while True:
            for customer in Customer.objects.iterator():
                # Only need to process timeouts for active customers

                if not (self.customer_is_active(customer) or self.customer_is_idle(customer)):
                    continue

                last_message = Message.objects.filter(
                    direction=0,
                    customer=customer.phone_number
                ).values('customer', 'date').order_by('-date').first()

                if last_message is None:
                    return

                time_delta = (utc.localize(datetime.datetime.now()) - last_message['date']).seconds

                if time_delta > self.cancel_timeout and self.customer_is_idle(customer):
                    if self.customer_needs_refund(customer):
                        self.do_refund(customer)
                        self.messenger.log_and_send_message(customer, customer.phone_number, ChatStrings.TIMEOUT_REFUND)
                    else:
                        self.set_customer_cancelled(customer)
                        self.messenger.log_and_send_message(customer, customer.phone_number,
                                                            ChatStrings.TIMEOUT_CANCELLED)

                if time_delta > self.idle_timeout and self.customer_is_active(customer):
                    self.set_customer_idle(customer)
                    self.messenger.log_and_send_message(customer, customer.phone_number, ChatStrings.TIMEOUT)
            time.sleep(self.schedule)
