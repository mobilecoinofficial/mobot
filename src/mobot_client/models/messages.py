#  Copyright (c) 2021 MobileCoin. All rights reserved.
from __future__ import annotations
import attr
import json
from typing import Optional, Callable
from datetime import datetime

import mc_util
from django.db import models
from django.db import transaction
from django.utils import timezone
from django.db.models import IntegerChoices
from phonenumber_field.modelfields import PhoneNumberField
from signald.types import Message as SignalMessage
from tenacity import wait_random_exponential, retry, retry_if_exception_type
from cached_property import threaded_cached_property_with_ttl


from mobot_client.models import Customer, Store, ConcurrentModificationException


class PaymentStatus(models.TextChoices):
    Failure = "Failure"
    TransactionPending = "TransactionPending"
    TransactionSuccess = "TransactionSuccess"


class SignalPayment(models.Model):
    note = models.TextField(help_text="Note sent with payment", blank=True, null=True)
    receipt = models.CharField(max_length=255, help_text="encoded receipt")

    def __str__(self):
        return f"{self.note} - {self.receipt}"


class Direction(models.IntegerChoices):
    RECEIVED = 0, 'received_from_customer'
    SENT = 1, 'sent_to_customer'


class Payment(models.Model):
    amount_mob = models.DecimalField(null=True, blank=True, decimal_places=8, max_digits=12, help_text="Amount of payment, if known")
    processed = models.DateTimeField(auto_now_add=True, help_text="The date a payment was processed, if it was.")
    updated = models.DateTimeField(auto_now=True, help_text="Time of last update")
    status = models.CharField(choices=PaymentStatus.choices, max_length=255, default=PaymentStatus.TransactionPending,
                              help_text="Status of payment")
    txo_id = models.CharField(max_length=255, null=True, blank=True)
    signal_payment = models.OneToOneField(SignalPayment, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False, blank=False, related_name='payments')

    def __str__(self):
        return f"Payment ({self.customer}) ({self.message.get_direction_display()}) ({self.amount_mob} PMOB)"


class RawMessageManager(models.Manager):
    def store_message(self, signal_message: SignalMessage) -> RawSignalMessage:
        if isinstance(signal_message.source, dict):
            number = signal_message.source['number']
        else:
            number = signal_message.source

        if signal_message.payment:
            payment = SignalPayment.objects.create(note=signal_message.payment.note,
                                                   receipt=signal_message.payment.receipt)
        else:
            payment = None

        raw = self.get_queryset().create(
            account=signal_message.username,
            source=number,
            timestamp=signal_message.timestamp,
            text=signal_message.text,
            raw=json.dumps(attr.asdict(signal_message)),
            payment=payment,
        )
        return raw


class RawSignalMessage(models.Model):
    '''A copy of the raw signal message'''
    account = PhoneNumberField(null=False, blank=False, help_text="Number of the receiver")
    source = PhoneNumberField(null=True, blank=True, help_text="Number associated with message, if it exists")
    timestamp = models.FloatField(help_text="Raw unix timestamp from the message data")
    text = models.TextField(help_text="Text body, if it exists", blank=True, null=True)
    raw = models.JSONField(help_text="The raw json sent")
    payment = models.OneToOneField(SignalPayment, on_delete=models.CASCADE, blank=True, null=True, help_text="Receipt object", related_name="signal_message")

    ### Manager to add custom creation/parsing
    objects = RawMessageManager()

    def __str__(self):
        return f"{'PAYMENT' if self.payment else ''} {self.source} -> {self.account}: '{self.text}'"


class MessageStatus(models.IntegerChoices):
    ERROR = -1
    NOT_PROCESSED = 0
    PROCESSING = 1
    PROCESSED = 2


class MessageQuerySet(models.QuerySet):
    def not_processing(self) -> models.QuerySet:
        return self.filter(status=MessageStatus.NOT_PROCESSED,
                           direction=Direction.RECEIVED).distinct('customer_id').order_by('customer_id', 'date', '-payment')

    @retry(wait=wait_random_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(ConcurrentModificationException))
    def get_optimistic(self, message: Message):
        updated = self.filter(pk=message.pk, status=MessageStatus.NOT_PROCESSED).select_for_update().update(status=MessageStatus.PROCESSING)
        if not updated:
            raise ConcurrentModificationException("Got a message currently being processed")
        message.refresh_from_db()
        return message

    @transaction.atomic()
    def get_message(self):
        if message := self.not_processing().first():
            return self.get_optimistic(message)


class MessageManager(models.Manager.from_queryset(MessageQuerySet)):

    @threaded_cached_property_with_ttl(ttl=5)
    def queue_size(self) -> int:
        return int(self.not_processing().all().count())

    def create_from_signal(self, signal_message: SignalMessage) -> Message:
        raw = RawSignalMessage.objects.store_message(signal_message=signal_message)
        dt = timezone.make_aware(datetime.fromtimestamp(float(signal_message.timestamp/1000)))
        store, _ = Store.objects.get_or_create(phone_number=raw.account)
        customer, _ = Customer.objects.get_or_create(phone_number=raw.source)
        stored_message = Message(
            customer=customer,
            text=signal_message.text,
            date=dt,
            direction=Direction.RECEIVED,
            store=store,
            raw=raw,
            status=MessageStatus.NOT_PROCESSED,
        )
        return stored_message


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField(default="", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    status = models.SmallIntegerField(choices=MessageStatus.choices, default=MessageStatus.NOT_PROCESSED)
    processing = models.DateTimeField(blank=True, null=True, help_text="The time we started processing a message")
    updated = models.DateTimeField(auto_now=True)
    direction = models.PositiveIntegerField(choices=Direction.choices, db_index=True)
    raw = models.OneToOneField(RawSignalMessage, on_delete=models.DO_NOTHING,
                               null=True,
                               blank=True,
                               related_name="parsed_message",
                               help_text="Reference to the raw message this was parsed from")
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True, related_name="message")
    ### Custom manager to create from signal and process payment ###
    objects = MessageManager()

    class Meta:
        ordering = ['customer_id', 'date', '-processing', 'updated']

    def __str__(self):
        return f'Message: customer: {self.customer} - {self.get_direction_display()} --- {self.text}'


class MobotResponse(models.Model):
    """The response to an incoming message or payment"""
    incoming = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True, related_name='responses')
    outgoing_response = models.OneToOneField(Message, on_delete=models.CASCADE, null=True, blank=True, related_name="response_message")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def customer(self):
        return self.incoming.customer.phone_number

    @property
    def incoming_text(self):
        return self.incoming.text

    @property
    def incoming_payment(self):
        if payment := self.incoming.payment:
            return mc_util.pmob2mob(self.incoming.payment.amount_mob)
        else:
            return 0

    @property
    def outgoing_payment(self):
        if payment := self.outgoing_response.payment:
            return mc_util.pmob2mob(payment.amount_mob)
        else:
            return 0

    def __str__(self):
        return f"MobotResponse: {self.incoming.customer}: {self.incoming.text} -> {self.outgoing_response.text}({self.outgoing_payment} MOB)"


class ProcessingError(models.Model):
    """Any errors in processing message"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="processing_errors", null=False, blank=False)
    exception = models.CharField(max_length=255, help_text="Exception Name")
    tb = models.TextField(help_text="Traceback or message", null=True, blank=True)
