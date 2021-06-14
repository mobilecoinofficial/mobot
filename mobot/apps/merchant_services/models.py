from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from djmoney.models.fields import MoneyField
from django.contrib.postgres.fields import ArrayField
from mobot.apps.signald_client import Signal
from mobot.apps.payment_service.models import Payment
from djmoney.contrib.exchange.models import convert_money


class UserAccount(models.Model):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField()

    class Meta:
        abstract = True
        app_label = 'merchant_services'
        ordering = ['name']

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
    class Meta(UserAccount.Meta):
        db_table = 'merchant_service_users'
    merchant_description = models.TextField(blank=True, default="A Mobot Merchant")


class Customer(UserAccount):
    class Meta(UserAccount.Meta):
        db_table = 'merchant_service_customers'
    received_sticker_pack = models.BooleanField(default=False)


class MCStore(models.Model):
    name = models.TextField()
    description = models.TextField(blank=True, default="Mobot Store")
    privacy_policy_url = models.URLField(blank=True, default="https://mobilecoin.com/privacy")
    merchant_ref = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="store_owner")

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class Product(models.Model):
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    name = models.TextField(blank=False)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.URLField(default=None, blank=True, null=True)
    number_restriction = ArrayField(models.TextField(blank=False, null=False), unique=False, blank=True, null=True)
    allows_refund = models.BooleanField(default=True, blank=False)
    price = MoneyField(max_digits=14, decimal_places=5, default_currency='GBP', help_text='Price of the product', blank=False, default=1.0)

    class Meta:
        app_label = 'merchant_services'
        unique_together = ('store_ref', 'name')
        abstract = True

    def __str__(self):
        return f'{self.store.name} - {self.name} - {self.price}'


class Drop(Product):
    pre_drop_description = models.TextField()
    advertisement_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    quota = models.PositiveIntegerField(default=10)  # Number left

    def __str__(self):
        return f'Store: {self.store_ref.name} - Name: {self.name} - Price: {self.price} - Start: {self.start_time} - Remaining: {self.quota}'


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()
    allows_payment = models.BooleanField()


class DropSession(models.Model):

    class SessionState(models.IntegerChoices):
        COMPLETED = -1
        STARTED = 0
        ALLOW_CONTACT_REQUESTED = 1
        EXPIRED = 2

    adjusted_price_pmob = models.PositiveIntegerField(blank=True, null=True, help_text="If we want to adjust the price to a target GBP, this is where it goes")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop_ref = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(default=0, choices=SessionState.choices)
    payment_ref = models.ForeignKey(Payment, blank=True, on_delete=models.CASCADE)
    refund = models.ForeignKey(Payment, blank=True, on_delete=models.CASCADE, related_name='refund')



class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()