from mobot.apps.merchant_services.models import User, Drop, DropSession
from mobot.apps.common.models import BaseMCModel
from typing import TypeVar, Set
import phonenumbers
import datetime
import pytz

from mobot.apps.merchant_services.validations import OneModelValidation, TwoModelValidation


class MockUser(BaseMCModel):
    def __init__(self, phone_number: str):
        self.phone_number: phonenumbers.PhoneNumber = phonenumbers.parse(phone_number)


class MockProduct(BaseMCModel):
    def __init__(self, name: str, inventory: int, price: float):
        self.name = name
        self.inventory = inventory
        self.price = price


class MockDrop(BaseMCModel):
    def __init__(self, country_codes_allowed: Set[str], product: MockProduct, start_time: datetime,
                 expires_after: datetime.timedelta):
        self.country_codes_allowed = country_codes_allowed
        self.product = product
        self.start_time = start_time
        self.expires_after = expires_after

    def still_going(self):
        return self.start_time + self.expires_after > datetime.datetime.now(tz=pytz.UTC())


class MockMerchant(BaseMCModel):
    def __init__(self, has_signal: bool):
        self.has_signal = has_signal


user1 = User("+44 7911 123456")
product1 = MockProduct(name="AirDrop1", inventory=5)
drop1 = MockDrop(country_codes_allowed={"+44"}, start_time=datetime.datetime.now(tz=pytz.UTC()),
                 expires_after=datetime.timedelta(days=1), product=product1)
drop2 = MockDrop(country_codes_allowed={"+44"}, start_time=datetime.datetime.now(tz=pytz.UTC()),
                 expires_after=datetime.timedelta(days=-1))


def check_has_number(u: MockUser) -> bool:
    return u.phone_number is not None


def check_number_country_code_matches_drop(u: MockUser, d: MockDrop):
    return u.phone_number.country_code in d.country_codes_allowed


def check_drop_still_active(d: MockDrop):
    return d.still_going()


def check_drop_still_has_inventory(d: MockDrop):
    return d.product.inventory > 0


def check_merchant_has_signal(m: MockMerchant):
    return m.has_signal

def check_user_has_not_gotten_coin(u: User, d: Drop):
    session = DropSession.objects.first(customer=u, product_ref=d)
    if session:
        if session.SessionState == session.SessionState.COMPLETED:
            return False
    return True

def check_user_has_gotten_coin(u: User, d: Drop):
    return not check_user_has_not_gotten_coin(u, d)

def check_funds_available(d: Drop):
    _funds_available(d.item_ref.price_in_picomob)

def _funds_available(account_id: str, amt_in_picomob: int) -> bool: ...

 # @christian: Can you confirm whether the explicit [MockUser] is necessary? Scala would infer it from the validator signature.
HAS_PHONE_NUMBER_VALIDATION = OneModelValidation[User](validator=check_has_number)
HAS_PHONE_NUMBER_VALIDATION.validate(user1)

COUNTRY_CODE_VALIDATION = TwoModelValidation[User, Drop](validator=check_number_country_code_matches_drop)
COUNTRY_CODE_VALIDATION.validate(user1, drop1)
HAS_ALREADY_GOTTEN_DROP = TwoModelValidation[User, Drop](validator=check_user_has_gotten_coin)

HAS_NOT_ALREADY_GOTTEN_DROP = TwoModelValidation[User, Drop](validator=check_user_has_not_gotten_coin)

FUNDS_ARE_AVAILABLE = OneModelValidation[Drop]

# bonus_validations = [HAS_ALREADY_GOTTEN_DROP(customer, original_drop), HAS_NOT_ALREADY_GOTTEN_DROP(customer, bonus_drop)]