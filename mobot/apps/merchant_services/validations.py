from mobot.apps.mobot_client.models import Drop, DropSession, Customer, BaseModel
from typing import TypeVar, Generic, Callable, Set
import phonenumbers
import datetime
import pytz


T = TypeVar('T', bound=BaseModel)
S = TypeVar('S', bound=BaseModel)
V = TypeVar('V', bound=BaseModel)


class MockUser(BaseModel):
    def __init__(self, phone_number: str):
        self.phone_number: phonenumbers.PhoneNumber = phonenumbers.parse(phone_number)


class MockProduct(BaseModel):
    def __init__(self, name: str, inventory: int, price: float):
        self.name = name
        self.inventory = inventory
        self.price = price


class MockDrop(BaseModel):
    def __init__(self, country_codes_allowed: Set[str], product: MockProduct, start_time: datetime,
                 expires_after: datetime.timedelta):
        self.country_codes_allowed = country_codes_allowed
        self.product = product
        self.start_time = start_time
        self.expires_after = expires_after

    def still_going(self):
        return self.start_time + self.expires_after > datetime.datetime.now(tz=pytz.UTC())


class MockMerchant(BaseModel):
    def __init__(self, has_signal: bool):
        self.has_signal = has_signal


class OneModelValidation(Generic[T]):

    def __init__(self, validator: Callable[[T], bool]):
        self.validator = validator

    def validate(self, arg: T) -> bool:
        return self.validator(arg)


class TwoModelValidation(Generic[T, V]):
    def __init__(self, validator: Callable[[T, V], bool]):
        self.validator = validator

    def validate(self, arg1: T, arg2: V) -> bool:
        return self.validator(arg1, arg2)


class ThreeModelValidation(Generic[T, V, S]):
    def __init__(self, validator: Callable[[T, V, S], bool]):
        self.validator = validator

    def validate(self, arg1: T, arg2: V, arg3: S) -> bool:
        return self.validator(arg1, arg2, arg3)


user1 = MockUser("+44 7911 123456")
product1 = MockProduct(name="AirDrop1", inventory=5)
drop1 = MockDrop(country_codes_allowed={"+44"}, start_time=datetime.datetime.now(tz=pytz.UTC()),
                 expires_after=datetime.timedelta(days=1))
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


has_phone_number_validation = OneModelValidation[MockUser](validator=check_has_number)
has_phone_number_validation.validate(user1)

country_code_validation = TwoModelValidation[MockUser, MockDrop](validator=check_number_country_code_matches_drop)
country_code_validation.validate(user1, drop1)
