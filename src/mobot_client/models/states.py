#  Copyright (c) 2021 MobileCoin. All rights reserved.

from django.db import models


class SessionState(models.IntegerChoices):
    IDLE_AND_REFUNDABLE = -4
    IDLE = -3
    REFUNDED = -2
    CANCELLED = -1, 'cancelled'
    READY = 0, 'ready_to_receive_initial'
    WAITING_FOR_PAYMENT_OR_BONUS_TX = 1, 'waiting_for_bonus_tx'
    WAITING_FOR_SIZE = 2, 'waiting_for_size'
    WAITING_FOR_NAME = 3
    WAITING_FOR_ADDRESS = 4
    SHIPPING_INFO_CONFIRMATION = 5
    ALLOW_CONTACT_REQUESTED = 6
    COMPLETED = 7

    @staticmethod
    def active_states():
        return {
            SessionState.READY,
            SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX,
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