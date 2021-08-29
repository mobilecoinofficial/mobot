# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
Set up a test drop, run the drop
"""
import pytz
from typing import Optional
from argparse import ArgumentParser
from dateutil.parser import parse
from django.utils import timezone
from datetime import timedelta, datetime
from logging import getLogger
from copy import copy
from mobot_client.models import Drop, ChatbotSettings, Store, DropType
from mobot_client.tests.factories import DropFactory, StoreFactory


from django.core.management.base import BaseCommand
from mobot_client.mobot import MOBot


def parse_duration(duration_string: str) -> timedelta:
    dt = datetime.strptime(duration_string, '%d:%H:%M:%S')
    return timedelta(days=dt.day, hours=dt.hour, minutes=dt.minute, seconds=dt.second)


def parse_date_utc(date_string: str):
    base_date = timezone.now() if not date_string else parse(date_string)
    return base_date.replace(tzinfo=pytz.UTC)


class Command(BaseCommand):
    help = 'Run Drop'

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '-s',
            '--store-number',
            type=str,
            help='Store phone number',
            default='+14152895764',
        )
        parser.add_argument(
            '-n',
            '--store-name',
            type=str,
            default='MOBot Shop'
        )
        parser.add_argument(
            '--store-description',
            type=str,
            default='MOBot Shop - Giving away money and selling hoodies since 2021!',
        )
        parser.add_argument(
            '--privacy-policy-url',
            type=str,
            default='https://my.mobotshop.com/privacy',
        )
        parser.add_argument(
            '--drop-description',
            type=str,
            default='MOBot Drop',
        )
        parser.add_argument(
            '--drop-name',
            type=str,
            default='MOBot Drop',
        )
        parser.add_argument(
            '-t',
            '--drop-type',
            type=lambda t: DropType[t],
            choices=['AIRDROP', 'ITEMDROP'],
            default=DropType.AIRDROP,
        )
        parser.add_argument(
            '-s',
            '--start-time',
            type=lambda d: parse_date_utc(d),
            default=None,
            required=False
        )
        parser.add_argument(
            '-d',
            '--duration',
            type=lambda d: parse_duration(d),
            help='drop duration in the format "%d:%H:%M:%S", for example "01:12:30:00" would be 1 day, 12 hours, 30 minutes, 0 seconds',
            default=timedelta(days=3),
        )

    def _process_args(self, options) -> dict:
        options = copy(options)
        options['end_time'] = options['start_time'] + options['duration']
        options['drop_name'] = f"{options['drop_name']} - {options['start_time'].strftime('%D')}"
        return options

    def handle(self, *args, **options):
        options = self._process_args(options)
        store = Store.objects.filter(phone_number=options['store_number']).first()
        if not store:
            store = Store.objects.create(name=options['store_name'],
                                         phone_number=options['store_number'],
                                         description=options['store_description'],
                                         privacy_policy_url=options['privacy_policy_url'])
        drop = Drop.objects.get_active_drop()

