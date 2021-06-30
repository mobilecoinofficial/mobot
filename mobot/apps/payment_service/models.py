from django.db import models


class Transaction(models.Model):
    class Status(models.IntegerChoices):
        TransactionSubmitted = -1
        TransactionPending = 0
        TransactionSuccess = 1
        Other = 2

    transaction_id = models.TextField(primary_key=True)
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
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

    def clean(self):
        if self.transaction.failed:
            self.status = Payment.Status.PAYMENT_FAILED
        elif self.transaction.pending:
            self.status = Payment.Status.PAYMENT_SUBMITTED
        elif self.transaction.completed:
            self.status = Payment.Status.PAYMENT_RECEIVED
        self.save()