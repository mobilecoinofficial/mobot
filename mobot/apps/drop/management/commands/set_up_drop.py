from django.core.management.base import BaseCommand, CommandError
from typing import Dict, Iterable, Optional
import phonenumbers
from phonenumbers import PhoneNumber
from mobot.lib.currency import *
from decimal import Decimal
from typedate import TypeDate
import sys

from django.conf import settings

from ..commands import *
import json
from enum import Enum


class DropManagmentActions(str, Enum):
    CREATE_STORE = 'create-store'
    ADD_INVENTORY = 'add-inventory'
    UPDATE_INVENTORY = 'update-inventory'
    ADD_PRODUCT = 'add-product'
    ADD_CAMPAIGN = 'add-campaign'  # Add a "drop"
    LIST_CAMPAIGNS = 'list-campaigns'
    ADD_MERCHANT = 'add-merchant'


class Command(BaseCommand):
    help = """
        Manage inventory for a drop. requires:
         --action: DropManagementAction, eg add-inventory
         --phone-number: PhoneNumber
         --product-name: name of the product - think 'MobileCoin Hoodie'
         
         Can use "--help" for more info.
         
         Inventory objects look like this: '{"S":10,"M":15,"L":12,"XL":10,"XXL":10}' and are parsed from a json
         string against mobot.campaigns.hoodies.Size enum.
         
         Probably won't handle a price adjustment well, as this expects the price to remain the same once created.
         TODO: @greg fix this in the future.
         
         usage will be something like:
          python mobot/manage.py set_up_drop -a add-product -p Hoodie # Prints out product group ID
          python mobot/manage.py set_up_drop -a create-store -s MobotShop -m "Greg Shopkeeper" -n +447441433907 -r +44 -d "Hoodie Store"
          python mobot/manage.py set_up_drop -a add-inventory -p Hoodie -i '{"S":10, "M":10, "L":10, "XL":10, "XXL":10}' --price 20 --currency GBP
          python mobot/manage.py set_up_drop -a add-campaign -c "Hoodie Drop" -p Hoodie --start-time '2021-07-30 00:00:00' --end-time '2021-08-02 00:00:00' --advertisement-start-time '2021-07-25 00:00:00'
        """

    def __init__(self, *args, **kwargs):
        self.product_group: Product = None
        self.store: MobotStore = None
        self.merchant: Merchant = None
        self.product_group: ProductGroup = None
        self.orders: Iterable[Order] = []
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('-a', '--action', choices=DropManagmentActions, type=DropManagmentActions, required=False,
                            default=DropManagmentActions.LIST_CAMPAIGNS)
        parser.add_argument('-p', '--phone-number', type=phonenumbers.parse,
                            required=False)  # Assume same as merchant for now
        parser.add_argument('-n', '--name', type=str, required=False)
        parser.add_argument('-q', '--quota', type=int,
                            help="Quota, if any, for number of people who can participate in campaign")
        parser.add_argument('-i', '--inventory', type=json.loads,
                            help="JSON of the inventory for the product at various sizes; e.g '{'S': 10, 'M': 10, 'L': 10 }'",
                            default='{}')
        parser.add_argument('-d', '--description', required=False)
        parser.add_argument('-r', '--number-restriction', required=False, type=str,
                            help="Country code restriction of product, eg 44")
        parser.add_argument('--reset', help="Reset all merchants, campaigns, products, inventory... Blank slate!",
                            action="store_true")
        parser.add_argument(
            '--start-time',
            help="start datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )
        parser.add_argument(
            '--end-time',
            help="end datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )
        parser.add_argument(
            '--advertisement-start-time',
            help="advertisement start datetime UTC",
            type=TypeDate('%Y-%m-%d %H:%M:%S', timezone='UTC'),
            required=False,
        )
        parser.add_argument('--price', required=False, type=Decimal)
        parser.add_argument('--currency', default=GBP)

    def _load_sizes(self, inventory: Dict[str, int]) -> Dict[Size, int]:
        """
        Args:
            inventory: A dictionary of size strings and the amount available

        Returns:
            dictionary of Size enums mapped to amount available
        """
        sized = dict()
        for key, value in inventory.items():
            sized[Size(key)] = value
        return sized

    def add_or_get_store(self, **options) -> MobotStore:
        phone_number = options.get("phone_number")
        name = options.get("name")
        description = options.get("description")
        merchant, _ = Merchant.objects.get_or_create(phone_number=phone_number)
        store, created = MobotStore.objects.get_or_create(name=name, merchant_ref=merchant, description=description)
        if created:
            if name:
                store.name = name
            store.save()
        return store

    def get_or_add_sized_product(self, product_group: ProductGroup, size: str,
                                 price: Money = Money(Decimal(25.0), currency=GBP)) -> Product:
        hoodie_product, created = Product.objects.get_or_create(
            name=f"{product_group.name}-{size}",
            price=price,
            description=f"{product_group.name}-{size}",
            product_group=product_group,
            store_ref=self.store,
            # Right now, there's just one store. For the future, this will need to be more flexible.
            metadata=dict(size=size)
        )
        return hoodie_product

    def add_customer_number_validation(self, campaign: Campaign, restriction: str):
        validation = Validation(model_class_name=Customer.__name__, model_attribute_name="phone_number",
                                comparator_func="startswith", target_value=f"+{restriction}")
        validation.save()
        campaign.validations.add(validation)
        return validation

    def add_merchant(self, **options):
        merchant = Merchant.objects.create(name=self.name, phone_number=self.phone_number)
        return merchant

    def add_campaign(self, **options) -> Campaign:
        campaign_name = self.name
        start_time = options.get('start_time')
        end_time = options.get('end_time')
        adv_start = options.get('advertisement_start_time')
        quota = options.get('quota')
        number_restriction = options.get('number_restriction').replace("+", "")  # Clean up the + if user adds it
        store = MobotStore.objects.get(merchant_ref__phone_number=self.phone_number)
        # Will fail if product group not created/given.
        product_group = ProductGroup.objects.get(name=self.product_name)

        campaign = Campaign.objects.create(
            name=campaign_name,
            store=store,
            advertisement_start_time=adv_start,
            pre_drop_description=options.get("description"),
            product_group=product_group,
            start_time=start_time,
            end_time=end_time,
            quota=quota,
            number_restriction=number_restriction,
        )

        if number_restriction:
            self.add_customer_number_validation(campaign=campaign, restriction=number_restriction)
            campaign.save()
        return campaign

    def reset(self):
        Merchant.objects.all().delete()
        MobotStore.objects.all().delete()
        InventoryItem.objects.all().delete()
        Product.objects.all().delete()
        ProductGroup.objects.all().delete()

    def handle(self, *args, **options):
        self.inventory = self._load_sizes(options['inventory'])
        self.name = options.get('name')
        self.phone_number = options.get('phone_number')
        self.action = options.get('action')
        self.merchant_name = options.get('merchant_name')
        self.store = None
        self.product_group = None

        if options.get("reset"):
            print("resetting all...")
            self.reset()

        price = options.get('price')
        currency = options['currency']  # safe as it has a default
        price_with_currency: Optional[Money] = None if not price else Money(price, currency)

        if self.action == DropManagmentActions.CREATE_STORE:
            self.store = self.add_or_get_store(**options)
            print(self.store)
            sys.exit(0)

        if self.action == DropManagmentActions.ADD_PRODUCT:
            self.product_group, created = ProductGroup.objects.get_or_create(name=self.product_name)
            print(f"{self.product_group} created with id {self.product_group.pk}")
            sys.exit(0)

        if self.action in (DropManagmentActions.UPDATE_INVENTORY, DropManagmentActions.ADD_INVENTORY):
            if not all(self.product_name, price, currency):
                raise CommandError("Lacking product inf")
            else:
                self.product_group = ProductGroup.objects.get(name=self.name)
                for size, amt_available in self.inventory:
                    product = self.get_or_add_sized_product(product_group=self.product_group, price=price_with_currency,
                                                            size=size)
                    if self.action == DropManagmentActions.ADD_INVENTORY:
                        product.add_inventory(amt_available)
                    else:
                        # Delete existing product inventory and update with current amounts
                        InventoryItem.objects.filter(product=product).delete()
                        product.add_inventory(amt_available)
            sys.exit(0)

        if self.action == DropManagmentActions.ADD_MERCHANT:
            merchant = self.add_merchant(merchant_name=self.name)
            print(f"{merchant} created with id {merchant.pk}")

        if self.action == DropManagmentActions.ADD_CAMPAIGN:
            campaign = self.add_campaign(options)
            print(f"{campaign} created with id {campaign.pk}")
            sys.exit(0)
