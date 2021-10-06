# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from concurrent.futures import as_completed
from typing import List, Dict
from collections import defaultdict
from django.test import LiveServerTestCase

import factory.random

from mobot_client.concurrency import AutoCleanupExecutor
from mobot_client.tests.factories import *

from mobot_client.models import (Drop,
                                 DropSession,
                                 Sku,
                                 DropType,
                                 BonusCoin,
                                 OutOfStockException)
from mobot_client.models.states import SessionState

factory.random.reseed_random('mobot cleanup')


class ModelTests(LiveServerTestCase):

    def setUp(self) -> None:
        self.logger = logging.getLogger("ModelTestsLogger")

    def test_items_available(self):
        '''Make sure inventory availability is what's expected, and sold-out logic is correctly applied'''
        store = StoreFactory.create()
        item = ItemFactory.create(store=store)
        drop = DropFactory.create(drop_type=DropType.ITEM, store=store, item=item)
        skus: Dict[str, Sku] = {sku.identifier: sku for sku in SkuFactory.create_batch(size=3, item=item, quantity=10)}

        for sku in skus.values():
            self.assertEqual(sku.number_available(), 10)

        self.assertEqual(item.skus.count(), 3)
        self.assertEqual(item.drops.count(), 1)

        self.logger.info("Creating sessions...")
        drop_sessions: List[DropSession] = list(DropSessionFactory.create_batch(size=10, drop=drop))
        for drop_session in drop_sessions:
            self.assertEqual(drop_session.drop, drop)

        orders = defaultdict(list)

        for count, drop_session in enumerate(drop_sessions):
            print(f"Creating order for drop session {drop_session.pk}")
            sku = list(skus.values())[count % 3]
            order = sku.order(drop_session)
            orders[sku.identifier].append(order)

        for sku in skus.values():
            self.assertEqual(sku.number_available(), (sku.quantity - sku.orders.count()))
            print("Cancelling an order to see if it affects sku availability")
            num_available_before_cancellation = sku.number_available()
            sku.orders.first().cancel()
            print(f"Order for sku {sku.identifier} cancelled by customer {order.customer}")
            self.assertEqual(sku.number_available(), num_available_before_cancellation + 1)

        print("Attempting to sell out a SKU...")

        new_sessions = list(DropSessionFactory.create_batch(size=7, drop=drop))
        sku_to_sell_out = list(skus.values())[0]
        order = None
        for session in new_sessions:
            order = sku_to_sell_out.order(session)
            print(f"Order confirmed. Inventory remaining for sku: {sku_to_sell_out.number_available()}")

        self.assertEqual(item.skus.count(), 2)

        print(f"Asserting {sku_to_sell_out} no longer in stock...")
        self.assertFalse(sku_to_sell_out.in_stock())
        sold_out_session = DropSessionFactory.create(drop=drop)

        with self.assertRaises(OutOfStockException):
            sku_to_sell_out.order(sold_out_session)
        print(f"Testing to see if cancelling an order puts item back in stock")
        order.cancel()
        self.assertTrue(sku_to_sell_out.in_stock())
        print(f"Trying to order previously sold-out session")
        self.assertIsNotNone(sku_to_sell_out.order(sold_out_session))
        print(f"Cancelled orders are available!")

    def test_claim_coin(self):
        '''Test that we're only able to claim a BonusCoin once'''
        drop = DropFactory.create(drop_type=DropType.AIRDROP)
        coin = BonusCoinFactory.create(drop=drop, number_available_at_start=1)
        session = DropSessionFactory.create(drop=drop)
        self.assertEqual(coin.number_remaining(), coin.number_available_at_start)
        claimed = BonusCoin.objects.claim_random_coin_for_session(drop_session=session)
        session.save()
        self.assertEqual(claimed.number_remaining(), claimed.number_available_at_start - 1)
        new_session = DropSessionFactory.create(drop=drop)
        with self.assertRaises(OutOfStockException):
            second_claimed = BonusCoin.objects.claim_random_coin_for_session(drop_session=session)
            session.save()
        self.assertEqual(BonusCoin.objects.available_coins().filter(drop=drop).count(), 0)

    def test_claim_multiple(self):
        '''Test several bonus coins to ensure random selection is able to find all available BonusCoins'''
        drop = DropFactory.create(drop_type=DropType.AIRDROP)
        coin = BonusCoinFactory.create_batch(size=2, drop=drop, number_available_at_start=1)
        session1 = DropSessionFactory.create(drop=drop)
        session2 = DropSessionFactory.create(drop=drop)
        session3 = DropSessionFactory.create(drop=drop)

        self.assertTrue(drop.under_quota())
        claimed1 = BonusCoin.objects.claim_random_coin_for_session(session1)
        claimed2 = BonusCoin.objects.claim_random_coin_for_session(session2)
        session1.save()
        session2.save()
        coins_available = BonusCoin.objects.available_coins().only('number_claimed').count()
        self.logger.info(f"After claiming two coins, number available: {coins_available}")
        self.assertEqual(BonusCoin.objects.available_coins().count(), 0)
        self.assertFalse(drop.under_quota())
        with self.assertRaises(OutOfStockException):
            BonusCoin.objects.claim_random_coin_for_session(session3)

    def test_claim_multithreaded(self):
        drop = DropFactory.create(drop_type=DropType.AIRDROP)
        coin = BonusCoinFactory.create_batch(size=3, drop=drop, number_available_at_start=10)
        futures = []

        with AutoCleanupExecutor(max_workers=10) as pool:
            # Try to claim more than we've got
            for i in range(35):
                fut = pool.submit(BonusCoin.objects.find_and_claim_unclaimed_coin, drop)
                futures.append(fut)

        for fut in as_completed(futures):
            print(fut.done())

        self.assertEqual(drop.num_bonus_sent(), 30)

    def test_active_drop_sessions_found_for_customer(self):
        '''Ensure that customers with old drop sessions don't find themselves unable to participate in current drops'''
        customer = CustomerFactory.create()
        new_session = DropSessionFactory.create(customer=customer)
        old_session = OldDropSessionFactory.create(customer=customer, state=SessionState.ALLOW_CONTACT_REQUESTED)

        self.assertTrue(new_session.drop.is_active())
        self.assertFalse(old_session.drop.is_active())

        actives = customer.active_drop_sessions()

        self.assertEqual(actives.count(), 1)
        print("Making sure we get the right drop session...")
        self.assertEqual(actives.first().pk, new_session.pk)
        print("Ending drop, making sure customer no longer sees it...")

        new_session.drop.start_time = timezone.now() - timedelta(days=5)
        new_session.drop.end_time = timezone.now() - timedelta(days=3)  # Sets the active drop to an end time before now
        new_session.drop.save()

        self.assertFalse(new_session.drop.is_active())
        self.assertEqual(customer.active_drop_sessions().count(), 0)

    def test_customer_has_completed_drop(self):
        '''Test that the has_completed_drop method returns as expected'''
        session = DropSessionFactory.create()
        customer = session.customer
        self.assertFalse(customer.has_completed_drop(session.drop))
        session.state = SessionState.COMPLETED
        session.save()
        self.assertTrue(customer.has_completed_drop(session.drop))

    def test_find_completed_and_errored_drops(self):
        '''
        Test that we're able to find drops in different states and that customer convenience methods return correct
        results
        '''
        customer = CustomerFactory.create()
        print("Making 5 completed sessions...")
        print(f"Made sessions {list(DropSessionFactory.create_batch(size=5, customer=customer, state=SessionState.COMPLETED))}")
        print("Making 1 errored session...")
        errored_session = DropSessionFactory.create(customer=customer, state=SessionState.OUT_OF_STOCK)
        print(f"Made session {errored_session} with OUT OF STOCK error")
        self.assertEqual(customer.errored_sessions().count(), 1)
        self.assertEqual(customer.fulfilled_drop_sessions().count(), 5)
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
        '''Test the customer.has_store_preferences method'''
        store = StoreFactory.create()
        customer = CustomerFactory.create()
        self.assertFalse(customer.has_store_preferences(store))
        prefs = CustomerStorePreferences.objects.create(store=store, customer=customer, allows_contact=True)
        self.assertTrue(customer.has_store_preferences(store))

    def test_customer_country_code_validity(self):
        '''Customer phone numbers outside of country code restrictions should not be valid for drops'''
        drop_single = DropFactory.create(number_restriction="+44")
        drop_none = DropFactory.create(number_restriction="")
        drop_list = DropFactory.create(number_restriction="+44,+49")

        us_customer: Customer = CustomerFactory.create(phone_number="+18054412655")
        uk_customer: Customer = CustomerFactory.create(phone_number="+447975777666")
        de_customer: Customer = CustomerFactory.create(phone_number="+4915735985797")

        self.assertTrue(uk_customer.matches_country_code_restriction(drop_single))
        self.assertTrue(uk_customer.matches_country_code_restriction(drop_none))
        self.assertTrue(uk_customer.matches_country_code_restriction(drop_list))
        
        self.assertFalse(us_customer.matches_country_code_restriction(drop_single))
        self.assertTrue(us_customer.matches_country_code_restriction(drop_none))
        self.assertFalse(us_customer.matches_country_code_restriction(drop_list))

        self.assertFalse(de_customer.matches_country_code_restriction(drop_single))
        self.assertTrue(de_customer.matches_country_code_restriction(drop_none))
        self.assertTrue(de_customer.matches_country_code_restriction(drop_list))

