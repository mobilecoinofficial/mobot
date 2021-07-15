from django.core.management.base import BaseCommand, CommandError
from typing import Dict, Iterable, Optional
import phonenumbers
from phonenumbers import PhoneNumber
from mobot.lib.currency import *
from decimal import Decimal
from django.conf import settings

from ..commands import *
import json
from enum import Enum


class DropManagmentActions(str, Enum):
    CREATE_STORE = 'create-store'
    ADD_INVENTORY = 'add-inventory'
    UPDATE_INVENTORY = 'update-inventory'
    ADD_PRODUCT = 'add-product'
    ADD_CAMPAIGN = 'add-campaign'

class Command(BaseCommand):
    help = """
        Manage inventory for a drop. requires:
         --action: DropManagementAction, eg add-inventory
         --store-phone-number: PhoneNumber
         --product-name: name of the product - think 'MobileCoin Hoodie'
         
         Inventory objects look like this: '{"S":10,"M":15,"L":12,"XL":10,"XXL":10}' and are parsed from a json
         string against mobot.campaigns.hoodies.Size enum.
         
         Probably won't handle a price adjustment well, as this expects the price to remain the same once created.
         TODO: @greg fix this in the future.
        """
    def __init__(self, *args, **kwargs):
        self.product: Product = None
        self.store: Store = None
        self.merchant: Merchant = None
        self.product_group: ProductGroup = None
        self.orders: Iterable[Order] = []
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('-a', '--action', choices=DropManagmentActions, type=DropManagmentActions)
        parser.add_argument('-n', '--store-phone-number', type=phonenumbers.parse, required=True)
        parser.add_argument('-s', '--store-name', type=str, required=False)
        parser.add_argument('-p', '--product-name', type=str, help="Name of the product group", required=False, default="Hoodie")
        parser.add_argument('-i', '--inventory', type=json.loads, help="JSON of the inventory for the product at various sizes; e.g '{'S': 10, 'M': 10, 'L': 10 }'", default='{}')
        parser.add_argument('-d', '--description', required=False)
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

    def add_or_get_store(self, phone_number: PhoneNumber = None, store_name: str = None) -> Store:
        store, created = Store.objects.get_or_create(phone_number=phone_number)
        if created:
            if store_name:
                store.name = store_name
            store.save()
        return store

    def add_products(self, product_group_name: str, inventory: Dict[Size, int]):
        pass

    def get_or_add_sized_product(self, product_group: ProductGroup, size: str, price: Money = Money(Decimal(25.0), currency=GBP)) -> Product:
        hoodie_product, created = Product.objects.get_or_create(
            name=f"Hoodie Size {size}",
            price=price,
            description=f"MobileCoin Hoodie {size}",
            product_group=product_group,
            store_ref=self.store,
            metadata=dict(size=size)
        )
        return hoodie_product

    def handle(self, *args, **options):
        self.inventory = self._load_sizes(options['inventory'])
        self.product_name = options.get('product_name')
        self.store_name = options.get('store_name')
        self.store_phone_number = options.get('store_phone_number')
        self.action = options.get('action')
        self.store = None
        self.product = None
        price = options.get('price')
        currency = options['currency'] # safe as it has a default
        price_with_currency: Optional[Money] = None if not price else Money(price, currency)

        if self.action == DropManagmentActions.CREATE_STORE:
            self.store = self.add_or_get_store(self.store_phone_number, self.store_name)

        if self.action == DropManagmentActions.ADD_PRODUCT:
            self.product, created = ProductGroup.objects.get_or_create(name=self.product_name)

        if self.action in (DropManagmentActions.UPDATE_INVENTORY, DropManagmentActions.ADD_INVENTORY):
            if not all(self.product_name, price, currency):
                raise CommandError("Lacking product inf")
            else:
                self.product_group = ProductGroup.objects.get(name=self.product_name)
                for size, amt_available in self.inventory:
                    product = self.get_or_add_sized_product(product_group=self.product_group, price=price_with_currency, size=size)
                    if self.action == DropManagmentActions.ADD_INVENTORY:
                        product.add_inventory(amt_available)
                    else:
                        # Delete existing product inventory and update with current amounts
                        InventoryItem.objects.filter(product=product).delete()
                        product.add_inventory(amt_available)


