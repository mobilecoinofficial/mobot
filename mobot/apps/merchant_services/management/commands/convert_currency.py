from django.core.management.base import BaseCommand
from argparse import ArgumentParser
from mobot.apps.merchant_services.ftx import PriceAPI
from moneyed import Money, Currency


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--from", type=str, default="GBP")
        parser.add_argument("--value", type=float, default=1.0)
        parser.add_argument("--to", type=str, default="MOB")

    def handle(self, *args, **options):
        from_curr = options['from']
        to_curr = options['to']
        value = options['value']
        original = Money(value, currency=from_curr)
        p = PriceAPI()
        print(p.convert(original, Currency(to_curr)))