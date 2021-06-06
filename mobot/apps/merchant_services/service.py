from typing import Protocol, Generic, TypeVar, List
from asyncio import Future
from models import Customer, Drop, DropSession
from mobot.apps.payment_service import PaymentService
from mobot.apps.payment_service.models import Payment


## Todo: Make this Async
class MerchantService(Protocol):
    payment_service: PaymentService

    def find_drops_for_user(self, customer: Customer) -> List[Drop]: ...

    def propose_drop_to_customer(self, customer: Customer, drop: Drop) -> List[Drop]: ...

    def begin_drop_session_with_customer(self, customer: Customer, drop: Drop) -> DropSession: ...

    def refund_drop_session(self, drop_session: DropSession) -> Payment: ...
