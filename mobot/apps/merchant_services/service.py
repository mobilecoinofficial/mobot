from typing import Protocol, Generic, TypeVar, List, Optional
from asyncio import Future
from models import Customer, Drop, DropSession
from mobot.apps.payment_service.service import PaymentService
from mobot.apps.payment_service.models import Payment
from mobot.apps.signald_client import Signal
from validations import TwoModelValidation


## Todo: Make this Async
class DropService:
    payment_service: PaymentService
    signald_client: Signal

    def add_customer(self, name: str, phone_number: str) -> Customer:
        cust = Customer.objects.get_or_create(name=name, phone_number=phone_number)
        return cust

    def find_single_drop_for_user(self, customer: Customer, drop: Drop, validations: List[TwoModelValidation[Customer, Drop]]) -> Optional[Drop]:
        found_drop = None
        validated = True
        for validation in validations:
            if not validated:
                break
            validated = validation.validate(customer, drop)
        if validated:
            return drop
        return None

    def find_available_drops_for_user(self, customer: Customer) -> List[Drop]:
        drops = Drop.objects.get()

        pass

    def propose_drop_to_customer(self, customer: Customer, drop: Drop) -> List[Drop]: ...

    def begin_drop_session_with_customer(self, customer: Customer, drop: Drop) -> DropSession: ...

    def refund_drop_session(self, drop_session: DropSession) -> Payment: ...



if __name__ == "__main__":
    ORIGINAL_AIRDROP_ID = 123
    BONUS_DROP_ID = 456
    CUSTOMER_PHONE_NUMBER = "+44 7911 123456"
    cust = Customer.objects.get(phone_number=CUSTOMER_PHONE_NUMBER)
    drop = Drop.objects.get(id=ORIGINAL_AIRDROP_ID)
    drop_service = DropService()

    maybe_original_drop = merchant_services.find_single_drop_for_user(cust, drop)
