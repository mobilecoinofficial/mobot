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
                                 OrderStatus, OutOfStockException)
from mobot_client.models.states import SessionState


class ModelTests(TestCase):


    def test_items_available(self):
        store = StoreFactory.create()
        item = ItemFactory.create(store=store)
        drop = DropFactory.create(drop_type=DropType.ITEM, store=store, item=item)
        skus: Dict[str, Sku] = {sku.identifier: sku for sku in SkuFactory.create_batch(size=3, item=item, quantity=10)}

        for sku in skus.values():
            self.assertEqual(sku.number_available(), 10)

        self.assertEqual(item.available_skus().count(), 3)
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
        order = None
        for session in new_sessions:
            order = Order.objects.create(
                customer=session.customer,
                drop_session=session,
                sku=sku_to_sell_out,
                status=OrderStatus.CONFIRMED,
            )
            print(f"Order confirmed. Inventory remaining for sku: {sku_to_sell_out.number_available()}")

        self.assertEqual(item.available_skus().count(), 2)

        print(f"Asserting {sku_to_sell_out} no longer in stock...")
        self.assertFalse(sku_to_sell_out.in_stock())
        print(f"Testing to see if cancelling an order puts item back in stock")
        order.status = OrderStatus.CANCELLED
        order.save()
        self.assertTrue(sku_to_sell_out.in_stock())
        print(f"Cancelled orders are available!")


    def test_airdrop_inventory(self):
        drop = DropFactory.create(drop_type=DropType.AIRDROP)
        print("Minting 3 BonusCoins")
        coins = BonusCoinFactory.create_batch(size=3, drop=drop)
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

        coins_available = sum(map(lambda c: c.number_remaining(), coins))
        print(f"Before clearing inventory, we had {coins_available} coins available")
        print("Making 100 sessions, clearing out inventory")
        more_sessions = DropSessionFactory.create_batch(size=25, drop=drop)
        coins_claimed = 0

        for num, session in enumerate(more_sessions):
            if coins_claimed < coins_available:
                self.assertEqual(session.drop.coins_available(), coins_available - coins_claimed)
                coin = BonusCoin.available.claim_random_coin(session)
                coins_claimed += 1
            else:
                with self.assertRaises(OutOfStockException):
                    BonusCoin.available.claim_random_coin(session)
        self.assertEqual(coins_claimed, coins_available)
        print(f"{coins_claimed} coins claimed by remaining sessions")


    def test_active_drop_sessions_found_for_customer(self):
        customer = CustomerFactory.create()
        new_session = DropSessionFactory.create(customer=customer)
        old_session = OldDropSessionFactory.create(customer=customer, state=SessionState.ALLOW_CONTACT_REQUESTED)

        self.assertTrue(new_session.drop.is_active())
        self.assertFalse(old_session.drop.is_active())

        print(DropSession.active_sessions)

        actives = customer.active_drop_sessions()

        self.assertEqual(actives.count(), 1)
        print("Making sure we get the right drop session...")
        self.assertEqual(actives.first().pk, new_session.pk)
        print("Ending drop, making sure customer no longer sees it...")

        new_session.drop.end_time = timezone.now() - timedelta(days=3) # Sets the active drop to an end time before now
        new_session.drop.save()

        self.assertFalse(new_session.drop.is_active())
        self.assertEqual(customer.active_drop_sessions().count(), 0)

    def test_customer_has_completed_drop(self):
        session = DropSessionFactory.create()
        customer = session.customer
        self.assertFalse(customer.has_completed_drop(session.drop))
        session.state = SessionState.COMPLETED
        session.save()
        self.assertTrue(customer.has_completed_drop(session.drop))

    def test_find_completed_and_errored_drops(self):
        customer = CustomerFactory.create()
        print("Making 5 completed sessions...")
        print(f"Made sessions {list(DropSessionFactory.create_batch(size=5, customer=customer, state=SessionState.COMPLETED))}")
        print("Making 1 errored session...")
        errored_session = DropSessionFactory.create(customer=customer, state=SessionState.OUT_OF_STOCK)
        print(f"Made session {errored_session} with OUT OF STOCK error")
        self.assertEqual(customer.errored_sessions().count(), 1)
        self.assertEqual(customer.completed_drop_sessions().count(), 6)
        self.assertEqual(customer.successful_sessions().count(), 5)
        self.assertEqual(customer.errored_sessions().first().drop.pk, errored_session.drop.pk)
        self.assertTrue(customer.has_completed_drop_with_error(errored_session.drop))

    def test_find_active_drop(self):
        print("Creating 10 inactive drops")
        inactive_drops = OldDropFactory.create_batch(size=10)
        active_drop = DropFactory.create()
        self.assertEqual(Drop.objects.count(), 11)
        # Assert that there's only one active drop
        self.assertEqual(Drop.objects.active_drops().count(), 1)
        self.assertEqual(Drop.objects.get_active_drop().pk, active_drop.pk)

    def test_customer_store_preferences_found(self):
        store = StoreFactory.create()
        customer = CustomerFactory.create()
        self.assertFalse(customer.has_store_preferences(store))
        prefs = CustomerStorePreferences.objects.create(store=store, customer=customer, allows_contact=True)
        self.assertTrue(customer.has_store_preferences(store))