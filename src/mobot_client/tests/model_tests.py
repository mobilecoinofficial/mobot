# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List, Dict
from collections import defaultdict
import unittest

from django.test import TestCase
import factory.random
from mobot_client.tests.factories import *

from django.db import transaction
import random

factory.random.reseed_random('mobot cleanup')

from mobot_client.models import (Drop,
                                 DropSession,
                                 Item,
                                 Sku,
                                 Customer,
                                 Store,
                                 DropType,
                                 BonusCoin,
                                 Order,
                                 OrderStatus)
from mobot_client.models.states import SessionState


class ModelTests(TestCase):


    def test_items_available(self):
        store = StoreFactory.create()
        item = ItemFactory.create(store=store)
        drop = DropFactory.create(drop_type=DropType.ITEM, store=store, item=item)
        skus: Dict[str, Sku] = {sku.identifier: sku for sku in SkuFactory.create_batch(size=3, item=item, quantity=10)}

        for sku in skus.values():
            self.assertEqual(sku.number_available(), 10)

        self.assertEqual(item.drops.count(), 1)

        print("Creating sessions...")
        drop_sessions: List[DropSession] = list(DropSessionFactory.create_batch(size=10, drop=drop))
        for drop_session in drop_sessions:
            self.assertEqual(drop_session.drop, drop)

        orders = defaultdict(list)

        for count, drop_session in enumerate(drop_sessions):
            print(f"Creating order for drop session {drop_session.pk}")
            order = Order.objects.create(
                customer=drop_session.customer,
                drop_session=drop_session,
                sku=list(skus.values())[count % 3],
                status=OrderStatus.CONFIRMED,
            )
            orders[sku.identifier].append(order)

        for sku in skus.values():
            self.assertEqual(sku.number_available(), (sku.quantity - sku.orders.count()))
            print("Cancelling an order to see if it affects sku availability")
            num_available_before_cancellation = sku.number_available()
            first_order = sku.orders.first()
            first_order.status = OrderStatus.CANCELLED
            first_order.save()
            print(f"Order for sku {sku.identifier} cancelled by customer {order.customer}")
            self.assertEqual(sku.number_available(), num_available_before_cancellation + 1)

        print("Attempting to sell out a SKU...")

        new_sessions = list(DropSessionFactory.create_batch(size=7, drop=drop))
        sku_to_sell_out = list(skus.values())[0]
        for session in new_sessions:
            order = Order.objects.create(
                customer=session.customer,
                drop_session=session,
                sku=sku_to_sell_out,
                status=OrderStatus.CONFIRMED,
            )
            print(f"Order confirmed. Inventory remaining for sku: {sku_to_sell_out.number_available()}")

        print(f"Asserting {sku_to_sell_out} no longer in stock...")
        self.assertFalse(sku_to_sell_out.in_stock())

    def test_airdrop_inventory(self):
        drop = DropFactory.create(drop_type=DropType.AIRDROP)
        print("Minting 3 BonusCoins")
        BonusCoinFactory.create_batch(size=3, drop=drop)
        sessions_by_coin: Dict[BonusCoin, List[DropSession]] = defaultdict(list)
        sessions = DropSessionFactory.create_batch(size=10, drop=drop)

        for session in sessions:
            coin = BonusCoin.available.claim_random_coin(session)
            print(f"Session {session.id} claimed coin {coin}")
            sessions_by_coin[coin].append(session)

        for coin, sessions in sessions_by_coin.items():
            print(f"Ensuring coin {coin.id} has been updated to show new availability...")
            print(f"Number of sessions claiming coin: {len(sessions)} Number available: {coin.number_remaining()}")
            self.assertEqual(coin.number_remaining(), coin.number_available_at_start - len(sessions))

        print("Making many sessions, clearing out inventory")
        more_sessions = DropSessionFactory.create_batch(size=100, drop=drop)



