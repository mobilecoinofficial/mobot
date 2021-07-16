import mobilecoin
from django.core.management.base import BaseCommand
from argparse import ArgumentParser
from mobot.apps.chat.chat_client import Mobot
from mobot.signald_client import Signal
from mobot.apps.merchant_services.models import Campaign, Merchant, MobotStore
from django.conf import settings


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--campaign-id", type=str, help="The campaign Mobot is serving")
        parser.add_argument("--store-id", type=float, help="The store Mobot is selling products from")

    def handle(self, *args, **options):
        campaign_id = options['campaign_id']
        store_id = options['store_id']
        campaign = Campaign.objects.get(id=campaign_id)
        store = MobotStore.objects.get(id=store_id)
        signal = Signal(str(MobotStore.merchant_ref.phone_number))
        fullservice_client = settings.fullservice
        chat = Mobot(signal=signal, mobilecoin_client=fullservice_client, campaign=campaign, store=store)
        chat.register_default_handlers()
        chat.run()