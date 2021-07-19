import mobilecoin
from django.core.management.base import BaseCommand
from argparse import ArgumentParser
from mobot.apps.chat.chat_client import Mobot
from mobot.signald_client import Signal
from mobot.apps.merchant_services.models import Campaign, Merchant, MobotStore
from django.conf import settings
import mobilecoin as mc
import time

class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--campaign-id", type=str, help="The campaign Mobot is serving")
        parser.add_argument("--store-id", type=float, help="The store Mobot is selling products from")

    def handle(self, *args, **options):
        campaign_id = options['campaign_id']
        store_id = options['store_id']
        campaign = Campaign.objects.get(pk=campaign_id)
        store = MobotStore.objects.get(pk=store_id)

        # FIXME: Should use env vars from settings
        mcc = mc.Client(url=f"http://host.docker.internal:9090/wallet") # FIXME: configurable (this is for mac)
        all_accounts_response = mcc.get_all_accounts()
        account_id = next(iter(all_accounts_response))
        account_obj = all_accounts_response[account_id]
        public_address = account_obj['main_address']

        signal = Signal(f"+{store.merchant_ref.phone_number.country_code}{store.merchant_ref.phone_number.national_number}",
                        socket_path=("host.docker.internal", 15432))
        signal.set_profile("MOBot TestNet", public_address, "logo.png", False)
        chat = Mobot(signal=signal, fullservice=mcc, campaign=campaign, store=store)
        chat.register_default_handlers()
        chat.run()
