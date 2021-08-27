#  Copyright (c) 2021 MobileCoin. All rights reserved.

from django.db import models


class SessionState(models.IntegerChoices):
    IDLE_AND_REFUNDABLE = -4
    IDLE = -3
    REFUNDED = -2
    CANCELLED = -1
    READY = 0
    WAITING_FOR_PAYMENT = 1, 'Waiting For Payment Or Bonus TX'
    WAITING_FOR_SIZE = 2
    WAITING_FOR_NAME = 3
    WAITING_FOR_ADDRESS = 4
    SHIPPING_INFO_CONFIRMATION = 5
    ALLOW_CONTACT_REQUESTED = 6
    # --- ANYTHING BELOW IS CONSIDERED COMPLETED --- #
    COMPLETED = 7
    CUSTOMER_DOES_NOT_MEET_RESTRICTIONS = 8  # Complete the session because
    OUT_OF_STOCK = 9, 'Out of Stock or MOB'# Unable to fulfill, our fault


    @staticmethod
    def active_states():
        return {
            SessionState.READY,
            SessionState.WAITING_FOR_PAYMENT,
            SessionState.ALLOW_CONTACT_REQUESTED,
            SessionState.WAITING_FOR_SIZE,
            SessionState.WAITING_FOR_ADDRESS,
            SessionState.WAITING_FOR_NAME,
            SessionState.SHIPPING_INFO_CONFIRMATION
        }
    
    @staticmethod
    @property
    def refundable_states():
        return {
            SessionState.IDLE_AND_REFUNDABLE,
            SessionState.WAITING_FOR_SIZE,
            SessionState.WAITING_FOR_ADDRESS,
            SessionState.WAITING_FOR_ADDRESS,
            SessionState.WAITING_FOR_NAME,
            SessionState.SHIPPING_INFO_CONFIRMATION
        }

    @staticmethod
    @property
    def error_states(self):
        return {SessionState.OUT_OF_STOCK}
