from mobot.apps.merchant_services.models import UserAccount, Drop, DropSession
from mobot.apps.common import models
from django.conf import settings
from typing import TypeVar, Set
import phonenumbers
import datetime
import pytz
import mobilecoin as fullservice

from mobot.apps.merchant_services.possible_validations import TwoModelValidation


class MockUser(models.Model):
    def __init__(self, phone_number: str):
        self.phone_number: phonenumbers.PhoneNumber = phonenumbers.parse(phone_number)


class MockProduct(models.Model):
    def __init__(self, name: str, inventory: int, price: float):
        self.name = name
        self.inventory = inventory
        self.price = price


class MockDrop(models.Model):
    def __init__(self, country_codes_allowed: Set[str], product: MockProduct, start_time: datetime,
                 expires_after: datetime.timedelta):
        self.country_codes_allowed = country_codes_allowed
        self.product = product
        self.start_time = start_time
        self.expires_after = expires_after

    def still_going(self):
        return self.start_time + self.expires_after > datetime.datetime.now(tz=pytz.UTC())


class MockMerchant(models.Model):
    def __init__(self, has_signal: bool):
        self.has_signal = has_signal


user1 = UserAccount("+44 7911 123456")
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

def check_user_has_not_gotten_coin(u: UserAccount, d: Drop):
    session = DropSession.objects.first(customer=u, product_ref=d)
    if session:
        if session.SessionState == session.SessionState.COMPLETED:
            return False
    return True

def check_user_has_gotten_coin(u: UserAccount, d: Drop):
    return not check_user_has_not_gotten_coin(u, d)

def check_funds_available(d: Drop):
    _funds_available(d.item_ref.price_in_picomob)

def _funds_available(amt_in_picomob: int) -> bool:
    fullservice_client = fullservice.Client(settings.FULLSERVICE_URL)
    account_balance_response = fullservice_client.get_balance_for_account(settings.ACCOUNT_ID)
    unspent_pmob = int(account_balance_response['result']['balance']['unspent_pmob'])
    return (amt_in_picomob + settings.FEE_PMOB) < unspent_pmob
