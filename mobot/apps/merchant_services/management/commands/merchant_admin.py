import argparse

from django.core.management.base import BaseCommand
from mobot.apps.merchant_services.models import Product, Merchant, MCStore, Drop

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
        merchant_subparser = parser.add_subparsers(title="merchant", help="merchant help")
        m_parser = merchant_subparser.add_parser("merchant")
        merchant_group = m_parser.add_argument_group(help="Merchant Help")

        merchant_group.add_argument(
            '--phone-number',
            type=str,
            help='add merchant by name and by phone number',
            required=True
        )
        merchant_group.add_argument(
            '--name',
            type=str,
            dest="merchant_name",
            help="Merchant name",
            required=True
        )

        store_subparser = parser.add_subparsers(title="store")
        s_parser = store_subparser.add_parser("store")
        store_group = s_parser.add_argument_group(help="Help with merchant commands")

        store_group.add_argument(
            '--number',
            type=str,
            dest="store_merchant_phone_number",
            help='add merchant by phone number',
            required=True
        )
        store_group.add_argument(
            '--name',
            type=str,
            dest="store_name",
            help="Merchant name",
            required=True
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

        product_subparser = parser.add_subparsers(title="product")
        p_parser = product_subparser.add_parser("product")
        product_group = p_parser.add_argument_group(help="Help with product commands")

        product_group.add_argument(
            '--name',
            dest="product_name",
            type=str,
            required=True,
        )
        product_group.add_argument(
            '--description',
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

    def handle(self, *args, **kwargs):
        try:
            parser = argparse.ArgumentParser()
            self.add_arguments(parser)

            args = parser.parse_args()
            args_data = vars(args)
            print(args_data)
        except KeyboardInterrupt as e:
            print()
            pass