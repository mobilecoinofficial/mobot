from moneyed import add_currency
from moneyed import Currency, GBP, USD, Money

MOB = add_currency(
    code='MOB',
    numeric=None,
    name='Mobilecoin'
)

PMOB = add_currency(
    code='PMB',
    numeric=None,
    name='Picomob'
)
