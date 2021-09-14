#  Copyright (c) 2021 MobileCoin. All rights reserved.
from __future__ import annotations

from typing import Optional, Callable
from datetime import datetime

from django.db import models
from django.db import transaction
from django.utils import timezone
from django.db.models import IntegerChoices
from signald.types import Message as SignalMessage

from mobot_client.models import Customer, Store


class PaymentStatus(models.TextChoices):
    FAILURE = "Failure"
    PENDING = "TransactionPending"
    SUCCESS = "TransactionSuccess"


class PaymentManager(models.Manager):
    def create_from_signal(self, message: SignalMessage, mcc: "mobot_client.payments.MCClient",
                           callback: Optional[Callable]) -> Payment:
        return mcc.process_receipt(message.source, message.payment.receipt, callback)


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
        return self.filter(status=MessageStatus.NOT_PROCESSED, direction=MessageDirection.RECEIVED).order_by('date',
                                                                                                             '-payment').all()

    @transaction.atomic
    def get_message(self):
        if message := self.not_processing().select_for_update().first():
            message.status = MessageStatus.PROCESSING
            message.processing = timezone.now()
            message.save()
            return message


class MessageManager(models.Manager.from_queryset(MessageQuerySet)):
    def create_from_signal(self, store: Store, mcc: "mobot_client.payments.MCClient", customer: Customer,
                           message: SignalMessage, callback: Optional[Callable] = None) -> Message:
        if message.payment:
            payment = Payment.objects.create_from_signal(message, mcc, callback)
        dt = timezone.make_aware(datetime.fromtimestamp(message.timestamp))
        message = self.get_queryset().create(
            customer=customer,
            text=message.text,
            date=dt,
            direction=MessageDirection.RECEIVED,
            store=store,
        )
        return message


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    status = models.SmallIntegerField(choices=MessageStatus.choices, default=MessageStatus.NOT_PROCESSED)
    processing = models.DateTimeField(blank=True, null=True, help_text="The time we started processing a message")
    updated = models.DateTimeField(auto_now=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices, db_index=True)

    ### Custom manager to create from signal and process payment ###
    objects = MessageManager()

    class Meta:
        ordering = ['date', '-processing', 'updated']

    def __str__(self):
        text_oneline = self.text.replace("\n", " ||| ")
        return f'Message: customer: {self.customer} - {self.direction} --- {text_oneline}'


class Payment(models.Model):
    amount_pmob = models.PositiveIntegerField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.DateTimeField(blank=True, null=True, help_text="The date a payment was processed, if it was.")
    updated = models.DateTimeField(auto_now=True, help_text="Time of last update")
    status = models.SmallIntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING,
                                      help_text="Status of payment")
    txo_id = models.CharField(max_length=255, null=True, blank=True)
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="payments")

    ### Custom Manager ###
    objects = PaymentManager()


class ReceiptType(models.IntegerChoices):
    FULL_SERVICE = 0
    SIGNAL = 1


class PaymentReceipt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='receipts')
    note = models.TextField(default=None, null=True, blank=True, help_text="The note that arrived with the payment")
    body = models.CharField(max_length=255)
    typ = models.IntegerField(choices=ReceiptType.choices, default=ReceiptType.SIGNAL)

    def get_amount_pmob(self) -> int:
        pass


class ProcessingError(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    text = models.TextField()


class MobotResponse(models.Model):
    """The response to an incoming message or payment"""
    incoming = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='responses', null=True,
                                 blank=True)
    response = models.OneToOneField(Message, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='response')
    created_at = models.DateTimeField(auto_now_add=True)