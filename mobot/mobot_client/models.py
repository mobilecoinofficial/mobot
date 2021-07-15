from django.db import models

# Create your models here.

class Store(models.Model):
    name = models.TextField()
    phone_number = models.TextField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f'{self.name} ({self.phone_number})'

class Item(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.TextField(default=None, blank=True, null=True)

    def __str__(self):
        return f'{self.name}'

class Drop(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    pre_drop_description = models.TextField()
    advertisment_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    number_restriction = models.TextField()
    timezone = models.TextField()
    initial_coin_amount_pmob = models.PositiveIntegerField(default=0)
    initial_coin_limit = models.PositiveIntegerField(default=0)
    conversion_rate_mob_to_currency = models.FloatField(default=1.0)
    currency_symbol = models.TextField(default="$")

    def value_in_currency(self, amount):
        return amount * self.conversion_rate_mob_to_currency

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'

class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available = models.PositiveIntegerField(default=0)

class Customer(models.Model):
    phone_number = models.TextField(primary_key=True)
    received_sticker_pack = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.phone_number}'

class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()

class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(default=0)
    bonus_coin_claimed = models.ForeignKey(BonusCoin, on_delete=models.CASCADE, default=None, blank=True, null=True)

class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()

#------------------------------------------------------------------------------------------

class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class  ChatbotSettings(SingletonModel):
    store = models.ForeignKey(Store, null=True, on_delete=models.SET_NULL)
    name = models.TextField()
    avatar_filename = models.TextField()

    def __str__(self):
        return "Global settings"