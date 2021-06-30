import datetime
import logging

import requests
from logging import getLogger
from mobot.lib.requests import retry_request
from djmoney.money import Money, Currency
from djmoney.contrib.exchange import backends
from djmoney.contrib.exchange.models import convert_money, Rate, ExchangeBackend
from mobot.settings import MOB, PMOB


class OpenExchangeRatesWithFtxBackend(backends.OpenExchangeRatesBackend):
    name = "openexchangewithcrypto"
    BASE_FTX_API = "https://ftx.com/api"

    def __init__(self, ftx_ttl: int = 300, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_rates()
        self.last_updated = datetime.datetime.utcnow().timestamp()
        self.ftx_ttl = ftx_ttl
        self.logger = getLogger("ExchangeRatesBackend")

    @retry_request
    def _get_ftx_usd_mob(self) -> requests.Response:
        """ Get the conversion rate of USD -> Mob from last traded price"""
        return requests.Request('GET', f"{self.BASE_FTX_API}/markets/MOB/USD")

    def _parse_ftx_rate(self, resp: requests.Response) -> float:
        """ Parse the FTX response """
        if resp.ok:
            if resp.json()['success']:
                return 1 / float(resp.json()['result']['last'])
            else:
                return 0.0
        else:
            self.logger.warning("Unable to update mob/usd rate!")

    def update_mob_price(self):
        """ We'd like these updated more frequently, so we've gotta be selective """
        if self.last_updated + self.ftx_ttl < datetime.datetime.utcnow().timestamp():
            mob_rate: float = self._parse_ftx_rate(self._get_ftx_usd_mob())
            backend, _ = ExchangeBackend.objects.update_or_create(name=self.name, defaults={"base_currency": "USD"})
            Rate.objects.update_or_create(Rate(currency=MOB.code, value=mob_rate, backend=backend))
            Rate.objects.update_or_create(Rate(currency=PMOB.code, value=mob_rate * 10 ** 12, backend=backend))

    def get_rates(self, **params):
        response = self.get_response(**params)
        base_usd_rates = self.parse_json(response)["rates"]
        mob_rate = self._parse_ftx_rate(self._get_ftx_usd_mob())
        base_usd_rates[MOB.code] = mob_rate
        base_usd_rates[PMOB.code] = mob_rate * 10 ** -12
        return base_usd_rates


class PriceAPI:
    logger = getLogger("PriceAPI")
    logger.setLevel(logging.INFO)

    def __init__(self, backend: OpenExchangeRatesWithFtxBackend = OpenExchangeRatesWithFtxBackend(), debug=False):
        self._rates_backend = backend
        if debug:
            self.logger.setLevel(logging.DEBUG)

    @property
    def last_updated(self) -> datetime:
        return datetime.datetime.utcfromtimestamp(self._rates_backend.last_updated)

    def convert(self, money: Money, target_currency: Currency) -> Money:
        self._rates_backend.update_mob_price()
        return convert_money(money, target_currency)
