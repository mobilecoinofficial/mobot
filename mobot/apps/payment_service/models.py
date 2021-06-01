from django.db import models
from djmoney.models.fields import MoneyField
from mobot.lib.currency import PMOB, MOB


class Transaction(models.Model):
    class Status(models.IntegerChoices):
        TransactionSubmitted = -1
        TransactionPending = 0
        TransactionSuccess = 1
        Other = 2

    transaction_amt = models.FloatField(default=0.0)
    transaction_status = models.IntegerField(choices=Status.choices, default=Status.TransactionSubmitted)
    receipt = models.TextField(blank=True)

    @property
    def completed(self):
        return self.transaction_status == self.Status.TransactionSuccess

    @property
    def pending(self):
        return self.transaction_status == self.Status.TransactionPending

    @property
    def failed(self):
        return self.transaction_status == self.Status.Other


class Payment(models.Model):

    class Status(models.IntegerChoices):
        PAYMENT_NOT_SUBMITTED = -1
        PAYMENT_SUBMITTED = 0
        PAYMENT_RECEIVED = 1
        PAYMENT_FAILED = 2

    status = models.IntegerField(choices=Status.choices, default=Status.PAYMENT_NOT_SUBMITTED)
    # FIXME: what are the right decimal places? For pmob, decimal_places could be 0, and max_digits would need to hold u64::max (20 digits)
    amount = MoneyField(max_digits=20, decimal_places=0, default_currency=PMOB, help_text='Price of the product in PMOB',
                       blank=False, default=0.0)

    def clean(self):
        if self.transaction.failed:
            self.status = Payment.Status.PAYMENT_FAILED
        elif self.transaction.pending:
            self.status = Payment.Status.PAYMENT_SUBMITTED
        elif self.transaction.completed:
            self.status = Payment.Status.PAYMENT_RECEIVED
        self.save()
