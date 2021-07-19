import argparse

import pytz
from django.core.management.base import BaseCommand
from mobot.apps.merchant_services.models import Product, Merchant, MobotStore, Campaign, ProductGroup, InventoryItem
from mobot.lib.currency import *
from django.utils import timezone as tz
from django.conf import settings
from typing import List
from typedate import TypeDate
from moneyed import Money, Currency, GBP
import datetime
from decimal import Decimal
from djmoney.contrib.exchange.models import convert_money


def parse_extra(parser, namespace):
    namespaces = []
    extra = namespace.extra
    while extra:
        n = parser.parse_args(extra)
        extra = n.extra
        namespaces.append(n)

    return namespaces

class Command(BaseCommand):
    help = 'Administer mobot store'

    def add_arguments(self, parser: argparse.ArgumentParser):
        # Named (optional) arguments

        merchant_group = parser.add_argument_group("Merchant Help")

        merchant_group.add_argument(
            '--phone-number',
            type=str,
            help='add merchant by name and by phone number',
            required=False
        )
        merchant_group.add_argument(
            '--name',
            type=str,
            dest="merchant_name",
            help="Merchant name",
            required=False,
            default="MobileCoin"
        )

        store_group = parser.add_argument_group("Help with store commands")

        store_group.add_argument(
            '--store-number',
            type=str,
            dest="store_merchant_phone_number",
            help='add merchant by phone number',
            required=False,
        )

        store_group.add_argument(
            '--store-name',
            type=str,
            dest="store_name",
            help="Merchant name",
            required=False
        )

        store_group.add_argument(
            "--description",
            type=str,
            dest="store_description",
            help="Description",
            required=False
        )

        store_group.add_argument(
            "-p",
            "--privacy-policy-url",
            dest="privacy_url",
            type=str,
            required=False,
        )

        product_group = parser.add_argument_group("Help with product commands")
        drop_group = parser.add_argument_group("Help with drop commands")


        product_group.add_argument(
            '--product-name',
            dest="product_name",
            type=str,
            required=False,
        )
        product_group.add_argument(
            '--product-description',
            dest="product_description",
            type=str,
            required=False
        )
        product_group.add_argument(
            '--image-link',
            dest="product_image_link",
            type=str,
            required=False
        )

        product_group.add_argument(
            '--price',
            help="Price in Picomob",
            type=int,
            required=False,
            default=0
        )
        product_group.add_argument(
            '-c',
            '--country-code-restrictions',
            help="Country codes (like +44) this is available for.",
            type=str,
            nargs="+",
        )
        product_group.add_argument(
            '-receipt',
            '--allows-refund',
            help="Product allows refund",
            action="store_true",
            default=False,
        )

        drop_group.add_argument(
            '--advertisement-start-time',
            help="advertising start datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )

        drop_group.add_argument(
            '--start-time',
            help="start datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )

        drop_group.add_argument(
            '--end-time',
            help="end datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )

        drop_group.add_argument("--reset-all-drops", required=False, action="store_true", default=False, help="Reset all accounts")

    def add_default_store(self, merchant: Merchant, **options) -> MobotStore:
        s, created = MobotStore.objects.get_or_create(merchant_ref=merchant, name="MobileCoin Hoodie Drop Store", description="We sell Hoodies!")
        s.save()
        return s

    def add_default_merchant(self, **options) -> Merchant:
        m, created = Merchant.objects.get_or_create(name="MobileCoin Official Merchant",
                                                    phone_number="+12252174798") #FIXME: settings.STORE_NUMBER)
        m.save()
        return m

    def add_default_product_group(self, store: MobotStore, **options) -> ProductGroup:
        p = ProductGroup(name="Hoodies")
        p.save()

        # Add inventory
        # FIXME: an issue with precision of pmob - needs to be able to handle 10^12
        small, created = Product.objects.get_or_create(name="Small", store=store, product_group=p, price=Decimal(1_000_000))
        small.add_inventory(10)

        medium, created = Product.objects.get_or_create(name="Medium", store=store, product_group=p, price=Decimal(1_000_000))
        medium.add_inventory(10)

        large, created = Product.objects.get_or_create(name="Large", store=store, product_group=p, price=Decimal(1_000_000))
        large.add_inventory(10)

        xlarge, created = Product.objects.get_or_create(name="XLarge", store=store, product_group=p, price=Decimal(1_000_000))
        xlarge.add_inventory(10)

        p.save()
        return p

    def create_default_campaign(self, product_group: ProductGroup, store: MobotStore) -> Campaign:
        c = Campaign.objects.create(
            name="MobileCoin Hoodie Sale",
            product_group=product_group,
            store=store,
            pre_drop_description="Sweet MobileCoin Hoodies",
            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
            adjusted_price=Money(20.0, GBP),
            number_restriction="1",
            quota=100)
        return c

    def make_mobot_default_store(self):
        print("TEST")

    def handle(self, *args, **options):
        try:
            if options.get("reset_all_drops"):
                Product.objects.all().delete()
                ProductGroup.objects.all().delete()
                InventoryItem.objects.all().delete()
                Merchant.objects.all().delete()
                MobotStore.objects.all().delete()
                Campaign.objects.all().delete()
            print("\033[1;33m ABOUT TO ADD MERCHANT\033[0m")
            merchant = self.add_default_merchant()
            print("\033[1;33m ADDED MERCHANT\033[0m")

            store = self.add_default_store(merchant)
            product_group = self.add_default_product_group(store)
            campaign = self.create_default_campaign(product_group, store)

            # drops = Drop.objects.all()
            # for drop in drops:
            #     print(drop)
            #     print(convert_money(drop.price, 'PMB'))
        except KeyboardInterrupt as e:
            print()
            pass
