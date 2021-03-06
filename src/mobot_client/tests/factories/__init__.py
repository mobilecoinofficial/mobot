#  Copyright (c) 2021 MobileCoin. All rights reserved.
from decimal import Decimal

import factory
import pytz
from django.utils import timezone
from datetime import timedelta
from faker.factory import Factory
from faker.providers import date_time, internet, phone_number, lorem

Faker = Factory.create
fake = Faker()
fake.add_provider(date_time)
fake.add_provider(internet)
fake.add_provider(phone_number)
fake.add_provider(lorem)
fake.seed(0)
dt = fake.date_time_between(start_date='+5d', end_date='+10d', tzinfo=pytz.utc)


from mobot_client.models import (
    Drop,
    Store,
    DropSession,
    SessionState,
    Customer,
    CustomerStorePreferences,
    Order,
    BonusCoin,
    DropType,
    Item,
    Sku,
)


class StoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Store
        django_get_or_create = ('phone_number',)

    id = factory.Faker('pyint')
    name = factory.Sequence(lambda n: f"Mobot Store #{n}")
    phone_number = factory.Sequence(lambda n: "+448211" + "%06d" % (n + 100000))
    description = fake.paragraph(nb_sentences=10)
    privacy_policy_url = factory.Sequence(lambda n: f"https://example.com/privacy_{n}")


class DropFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Drop

    drop_type = DropType.AIRDROP
    store = factory.SubFactory(StoreFactory)
    id = factory.Sequence(lambda n: n)
    pre_drop_description = factory.Sequence(lambda n: f"Item drop {n}")
    advertisment_start_time = fake.date_time_between(start_date='-2d', end_date='+10d', tzinfo=pytz.utc)
    start_time = timezone.now() - timedelta(days=2)
    end_time = timezone.now() + timedelta(days=2)
    number_restriction = factory.Iterator(['+44', '+1'])
    timezone = 'PST'
    initial_coin_amount_mob = Decimal(f"{float(0.2):4f}")

    @factory.lazy_attribute
    def store_id(self):
        return self.store.pk

    @factory.lazy_attribute
    def item_id(self):
        if hasattr(self, 'item'):
            return self.item.pk


class OldDropFactory(DropFactory):
    start_time = timezone.now() - timedelta(days=3)
    end_time = timezone.now() - timedelta(days=1)
    advertisment_start_time = fake.date_time_between(start_date='-15d', end_date='-1d', tzinfo=pytz.UTC)


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    @factory.post_generation
    def add_items_to_store(obj, created, *args, **kwargs):
        obj.store.items.add(obj)

    id = factory.Faker('pyint')
    name = f"{factory.Faker('name')}  {factory.Faker('sentence', nb_words=5)}"
    price_in_mob = factory.Faker('pydecimal', positive=True, left_digits=3, right_digits=6)

    description = factory.Faker('sentence', nb_words=50)
    short_description = factory.Faker('sentence', nb_words=10)
    image_link = factory.Sequence(lambda n: f"https://img.com/image{n}")
    store = factory.SubFactory(StoreFactory)

    @factory.lazy_attribute
    def store_id(self):
        return self.store.id



class SkuFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sku

    identifier = factory.Faker('pystr')


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        django_get_or_create = ('phone_number',)

    phone_number = factory.Sequence(lambda n: f"+447911" + "%06d" % (n + 100000))


class BonusCoinFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BonusCoin

    drop = factory.SubFactory(DropFactory, drop_type=DropType.AIRDROP)
    amount_mob = factory.Faker('pydecimal', positive=True, left_digits=3, right_digits=6)
    number_available_at_start = 10


class ItemDropFactory(DropFactory):
    drop_type = DropType.ITEM

class AirDropFactory(DropFactory):
    drop_type = DropType.AIRDROP


class DropSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DropSession

    customer = factory.SubFactory(CustomerFactory)
    drop = factory.SubFactory(DropFactory)


class OldDropSessionFactory(DropSessionFactory):
    drop = factory.SubFactory(OldDropFactory)


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
        inline_args = ('sku',)

    drop_session = factory.SubFactory(DropSessionFactory)

    @factory.lazy_attribute
    def customer(self):
        return self.drop_session.customer


class GenericItemDropFactory(factory.django.DjangoModelFactory):
    pass
