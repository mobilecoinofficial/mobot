from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.postgres.fields import ArrayField


from mobot.apps.signald_client import Signal
from mobot.apps.payment_service.models import Payment


class UserAccount(models.Model):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField()

    def __str__(self):
        return f'{self.phone_number}'

    def signal_payments_enabled(self, signal: Signal) -> bool:
        signal_profile = signal.get_profile_from_phone_number(self.phone_number)
        try:
            _customer_payments_address = signal_profile['data']['paymentsAddress']
            return True
        except:
            return False

    def payments_address(self, signal: Signal):
        signal_profile = signal.get_profile_from_phone_number(self.phone_number)
        try:
            customer_payments_address = signal_profile['data']['paymentsAddress']
            return customer_payments_address
        except Exception as e:
            return None


class Merchant(UserAccount):
    @property
    def account_id(self):
        return settings.ACCOUNT_ID


class MCStore(models.Model):
    name = models.TextField()
    description = models.TextField(blank=True, default="Mobot Store")
    privacy_policy_url = models.URLField(blank=True, default="https://mobilecoin.com/privacy")
    merchant_ref = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="store_owner")

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class Product(models.Model):
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.URLField(default=None, blank=True, null=True)
    number_restriction = ArrayField(models.TextField(blank=False, null=False), unique=True, blank=True)
    allows_refund = models.BooleanField(default=True, blank=False)
    price_in_picomob = models.IntegerField(default=0, null=False)

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Drop(Product):
    pre_drop_description = models.TextField()
    advertisement_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    quota = models.IntegerField(default=10)

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Airdrop(Drop):
    amount = models.FloatField()


class Customer(UserAccount):
    received_sticker_pack = models.BooleanField(default=False)


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()
    allows_payment = models.BooleanField()


class Session(models.Model):

    class SessionState(models.IntegerChoices):
        COMPLETED = -1
        STARTED = 0
        ALLOW_CONTACT_REQUESTED = 1
        EXPIRED = 2

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE)
    state = models.IntegerField(default=0, choices=SessionState.choices)
    payment_ref = models.ForeignKey(Payment, blank=True, on_delete=models.CASCADE)
    refund = models.ForeignKey(Payment, blank=True, on_delete=models.CASCADE, related_name='refund')


class DropSession(Session):
    pass


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()