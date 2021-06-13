import datetime
import logging

import forex_python.converter
import requests
from logging import getLogger
from mobot.lib.requests import retry_request
from forex_python.converter import CurrencyRates


class PriceAPI:
    BASE_FTX_API = "https://ftx.com/api"
    logger = getLogger("PriceAPI")
    logger.setLevel(logging.INFO)

    @staticmethod
    @retry_request
    def _get(url: str) -> requests.Response:
        request = requests.Request('get', url)
        return request

    def __init__(self, rate_ttl: int = 300, debug=False, rates_api: CurrencyRates = CurrencyRates()):
        self._mob_usd_rate = 0.0
        self._rate_ttl = rate_ttl
        self._forex_api = rates_api
        self._last_checked_mob_rate = datetime.datetime.utcnow().timestamp()
        self._last_checked_gbp_rate = datetime.datetime.utcnow().timestamp()
        self._usd_gbp_rate = None
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def get_usd_gbp_rate(self) -> float:
        try:
            return self._forex_api.get_rate("USD", "GBP")
        except forex_python.converter.RatesNotAvailableError:
            self.logger.exception("Unable to get GBP rate")


    @property
    def mob_usd_rate(self) -> float:
        if not self._mob_usd_rate or (self._last_checked_mob_rate + self._rate_ttl) < datetime.datetime.utcnow().timestamp():
            self.logger.info("Getting new rate for MOB/USD...")
            self._mob_usd_rate = self.last_mob_to_usd_rate()
            self.logger.info(f"MOB/USD rate: {self._mob_usd_rate}")
        return self._mob_usd_rate

    @property
    def usd_gbp_rate(self) -> float:
        if not self._usd_gbp_rate or (self._last_checked_gbp_rate + datetime.timedelta(days=1)) < datetime.datetime.utcnow().timestamp():
            self.logger.info("Getting new rate for GBP/USD...")
            self._usd_gbp_rate = self.get_usd_gbp_rate()
            self.logger.info(f"GBP/USD rate: {self._usd_gbp_rate}")
        return self._usd_gbp_rate

    def last_mob_to_usd_rate(self) -> float:
        result: requests.Response = self._get(f"{self.BASE_FTX_API}/markets/MOB/USD")
        if result.ok:
            if result.json()['success']:
                return float(result.json()['result']['last'])
            else:
                return 0.0
        else:
            self.logger.warning("Unable to update mob/usd rate")

    def picomob_to_gbp(self, amt_picomob: int) -> float:
        amt_mob = amt_picomob/(10**12)
        return self.mob_usd_rate * amt_mob * self.usd_gbp_rate

    def gbp_to_picomob(self, amt_gbp: float) -> int:
        amt_usd = amt_gbp / self.usd_gbp_rate
        amt_mob = amt_usd / self.mob_usd_rate
        return int(amt_mob * 10 ** 12)