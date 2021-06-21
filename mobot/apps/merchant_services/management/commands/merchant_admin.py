import argparse

import pytz
from django.core.management.base import BaseCommand
from mobot.apps.merchant_services.models import Product, Merchant, MCStore, Drop
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
            '-r',
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


    def add_default_store(self, merchant: Merchant, **options) -> MCStore:
        s, created = MCStore.objects.get_or_create(merchant_ref=merchant, name="MobileCoin Coin Drop Store")
        s.save()
        return s

    def add_default_merchant(self, **options) -> Merchant:
        m, created = Merchant.objects.get_or_create(name="MobileCoin Official Merchant", phone_number=settings.STORE_NUMBER)
        m.save()
        return m

    def add_default_drops(self, store: MCStore, **options) -> List[Drop]:
        Drop.objects.filter(name__startswith="Initial Airdrop", store_ref=store).delete()
        original_drop, _ = Drop.objects.update_or_create(name="Initial AirDrop",
                            pre_drop_description="Get free MOB from MobileCoin!",
                            store_ref=store,
                            description="My Store",
                            number_restriction=["+44"],
                            advertisement_start_time=datetime.datetime.utcnow(),
                            start_time=datetime.datetime.utcnow(),
                            end_time=datetime.datetime.utcnow() + datetime.timedelta(days=3.0),
                            price=Money(Decimal(3.0), GBP),
                            quota=100)

        dropped = Drop.objects.filter(name__startswith="Bonus AirDrop").delete()

        bonus_drops = [Drop.objects.update_or_create(name=f"Bonus AirDrop {price}",
                            pre_drop_description="Get free MOB from MobileCoin!",
                            store_ref=store,
                            description="My Store",
                            number_restriction=["+44"],
                            advertisement_start_time=datetime.datetime.utcnow(),
                            start_time=datetime.datetime.utcnow(),
                            end_time=datetime.datetime.utcnow() + datetime.timedelta(days=3.0),
                            quota=quota,
                            price=Money(Decimal(price), GBP)) for quota, price in [(80, 2.0), (10, 7.0), (7, 22.0), (3, 47)]]
        print(original_drop)
        for bonus in bonus_drops:
            print(bonus)
        return original_drop, bonus_drops

    def make_mobot_default_store(self):
        pass

    def handle(self, *args, **options):
        try:
            if options.get("reset_all_drops"):
                Merchant.objects.all().delete()
                MCStore.objects.all().delete()
                Drop.objects.all().delete()
                merchant = self.add_default_merchant()
                store = self.add_default_store(merchant)
                airdrop, bonus_drops = self.add_default_drops(store)
            drops = Drop.objects.all()
            for drop in drops:
                print(drop)
                print(convert_money(drop.price, 'PMB'))
        except KeyboardInterrupt as e:
            print()
            pass