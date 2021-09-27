#  Copyright (c) 2021 MobileCoin. All rights reserved.
from django.db.transaction import DatabaseError


class ConcurrentModificationException(DatabaseError):
    """Raise if we're unable to update a coin with optimistic locking"""
    pass