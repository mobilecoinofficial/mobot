from typing import Protocol, Generic, TypeVar, List
from asyncio import Future
from models import Customer, Drop
from mobot.apps.payment_service import PaymentService


class MerchantService(Protocol):
    payment_service: PaymentService

    def find_drops_for_user(self, customer: Customer, drop: Drop) -> Future[List[Drop]]:
