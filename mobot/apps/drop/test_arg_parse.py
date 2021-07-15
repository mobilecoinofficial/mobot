import argparse
import json
import phonenumbers
from mobot.lib.currency import *
from decimal import Decimal
from mobot.campaigns.hoodies import Size
from typing import Dict


def load_sizes(inventory: Dict[str, int]) -> Dict[Size, int]:
    sized = dict()
    for key, value in inventory.items():
        sized[Size(key)] = value
    return sized

def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('-n', '--store-phone-number', type=phonenumbers.parse, required=False)
    parser.add_argument('-s', '--store-name', type=str, required=False)
    parser.add_argument('-p', '--product-name', type=str, help="Name of the product group", default="Hoodie")
    parser.add_argument('-i', '--inventory',
                        type=json.loads,
                        help="JSON of the inventory for the product at various sizes; e.g '{'S': 10, 'M': 10, 'L': 10 }'",
                        default='{}')
    parser.add_argument('--price', type=Decimal, required=False, default=Decimal(10.0))
    parser.add_argument('--currency', type=Currency, default=GBP)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    args.inventory = load_sizes(args.inventory)
    print(args.inventory)
    print(Money(args.price, args.currency))
