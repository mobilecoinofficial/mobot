#  Copyright (c) 2021 MobileCoin. All rights reserved.

from django.db.models import IntegerChoices


class PaymentStatus(IntegerChoices):
    EXCESS_PAYMENT_WILL_REFUND = 0
    EXCESS_PAYMENT_NOT_ENOUGH_TO_REFUND = 1
