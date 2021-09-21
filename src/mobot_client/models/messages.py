#  Copyright (c) 2021 MobileCoin. All rights reserved.
from __future__ import annotations
import attr
import json
from typing import Optional, Callable
from datetime import datetime

from django.db import models
from django.db import transaction
from django.utils import timezone
from django.db.models import IntegerChoices
from phonenumber_field.modelfields import PhoneNumberField
from signald.types import Message as SignalMessage

from mobot_client.models import Customer, Store



class PaymentStatus(models.TextChoices):
    Failure = "Failure"
    TransactionPending = "TransactionPending"
    TransactionSuccess = "TransactionSuccess"


class SignalPayment(models.Model):
    note = models.TextField(help_text="Note sent with payment", blank=True, null=True)
    receipt = models.CharField(max_length=255, help_text="encoded receipt")


class Payment(models.Model):
    amount_pmob = models.PositiveIntegerField(null=True, blank=True, help_text="Amount of payment, if known")
    processed = models.DateTimeField(auto_now_add=True, help_text="The date a payment was processed, if it was.")
    updated = models.DateTimeField(auto_now=True, help_text="Time of last update")
    status = models.CharField(choices=PaymentStatus.choices, max_length=255, default=PaymentStatus.TransactionPending,
                              help_text="Status of payment")
    txo_id = models.CharField(max_length=255, null=False, blank=False)
    signal_payment = models.OneToOneField(SignalPayment, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Payment ({self.message.customer}) ({self.amount_pmob} PMOB)"


class PaymentVerification(models.Model):
    payment = models.OneToOneField(SignalPayment, on_delete=models.CASCADE, blank=False, null=False, help_text="The raw payment receipt")
    error = models.TextField(blank=True, null=True, help_text="An error, if it exists")
    successful = models.BooleanField(blank=False, null=False, default=True)


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
    timestamp = models.IntegerField(help_text="Raw unix timestamp from the message data")
    text = models.TextField(help_text="Text body, if it exists", blank=True, null=True)
    raw = models.JSONField(help_text="The raw json sent")
    payment = models.OneToOneField(SignalPayment, on_delete=models.CASCADE, blank=True, null=True, help_text="Receipt object", related_name="signal_message")

    ### Manager to add custom creation/parsing
    objects = RawMessageManager()


class MessageStatus(models.IntegerChoices):
    ERROR = -1
    NOT_PROCESSED = 0
    PROCESSING = 1
    PROCESSED = 2


class MessageDirection(models.IntegerChoices):
    RECEIVED = 0, 'received_from_customer'
    SENT = 1, 'sent_to_customer'


class MessageQuerySet(models.QuerySet):
    def not_processing(self) -> models.QuerySet:
        return self.filter(status=MessageStatus.NOT_PROCESSED,
                           direction=MessageDirection.RECEIVED)\
                    .order_by('date', '-payment')\
                    .distinct('customer_id')

    @transaction.atomic
    def get_message(self):
        if message := self.not_processing().select_for_update().first():
            message.status = MessageStatus.PROCESSING
            message.processing = timezone.now()
            message.save()
            return message


class MessageManager(models.Manager.from_queryset(MessageQuerySet)):

    def create_from_signal(self, signal_message: SignalMessage) -> Message:
        raw = RawSignalMessage.objects.store_message(signal_message=signal_message)
        dt = timezone.make_aware(datetime.fromtimestamp(float(signal_message.timestamp/1000)))
        store, _ = Store.objects.get_or_create(phone_number=raw.account)
        customer, _ = Customer.objects.get_or_create(phone_number=raw.source)
        stored_message = self.get_queryset().create(
            customer=customer,
            text=signal_message.text,
            date=dt,
            direction=MessageDirection.RECEIVED,
            store=store,
            raw=raw,
            status=MessageStatus.NOT_PROCESSED,
        )
        return stored_message


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    status = models.SmallIntegerField(choices=MessageStatus.choices, default=MessageStatus.NOT_PROCESSED)
    processing = models.DateTimeField(blank=True, null=True, help_text="The time we started processing a message")
    updated = models.DateTimeField(auto_now=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices, db_index=True)
    raw = models.OneToOneField(RawSignalMessage, on_delete=models.DO_NOTHING,
                               null=True,
                               blank=True,
                               related_name="parsed_message",
                               help_text="Reference to the raw message this was parsed from")
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True)
    ### Custom manager to create from signal and process payment ###
    objects = MessageManager()

    class Meta:
        ordering = ['date', '-processing', 'updated']

    def __str__(self):
        text_oneline = self.text.replace("\n", " ||| ")
        return f'Message: customer: {self.customer} - {self.direction} --- {text_oneline}'


class MobotResponse(models.Model):
    """The response to an incoming message or payment"""
    incoming = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='responses', null=True, blank=True)
    response = models.OneToOneField(Message, on_delete=models.CASCADE, null=True, blank=True, related_name='response')
    created_at = models.DateTimeField(auto_now_add=True)


class ProcessingError(models.Model):
    """Any errors in processing message"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="processing_errors", null=False, blank=False)
    exception = models.CharField(max_length=255, help_text="Exception Name")
    tb = models.TextField(help_text="Traceback or message", null=True, blank=True)
