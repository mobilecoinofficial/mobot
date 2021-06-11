import datetime
import logging
import requests
from typing import Optional
from logging import getLogger
from django.conf import settings

FREE_KEY = settings.CURR_FREE_KEY
PAID_KEY = settings.CURR_PAID_KEY


class PriceAPI:
    BASE_FTX_API = "https://ftx.com/api"
    BASE_FREE_CONVERTER_API = "https://free.currconv.com"
    BASE_PAID_CONVERTER_API = "https://prepaid.currconv.com"
    logger = getLogger("PriceAPI")
    logger.setLevel(logging.DEBUG)

    @staticmethod
    def _converter_url(free: bool = True) -> str:
        key = FREE_KEY if free else PAID_KEY
        base = PriceAPI.BASE_FREE_CONVERTER_API if free else PriceAPI.BASE_PAID_CONVERTER_API
        return f"{base}/api/v7/convert?q=USD_GBP&compact=ultra&apiKey={key}"

    @staticmethod
    def _get_url(url: str) -> Optional[dict]:
        resp: Optional[requests.Response] = None
        try:
            logging.debug(url)
            resp = requests.get(url)
        except requests.exceptions.RequestException:
            PriceAPI.logger.exception(f"Request Exception getting {url}")
        if resp:
            try:
                return resp.json()
            except ValueError:
                PriceAPI.logger.exception(f"Unable to decode json from {url}")
        return None

    @staticmethod
    def _get_usd_gbp_rate(free=True) -> float:
        if not free:
            PriceAPI.logger.warning("!!! Using paid API for USD-GBP rate !!!")
        price_response = PriceAPI._get_url(PriceAPI._converter_url(free))
        if not price_response:
            PriceAPI.logger.error("Unable to get free USD-GBP rate")
            price_response = PriceAPI._get_usd_gbp_rate(False)
        if price_response:
            PriceAPI.logger.debug(price_response)
            return float(price_response['USD_GBP'])

    def __init__(self, rate_ttl: int = 300):
        self._mob_usd_rate = 0.0
        self._rate_ttl = rate_ttl
        self._last_checked =  datetime.datetime.utcnow().timestamp()
        self.usd_gbp_rate = PriceAPI._get_usd_gbp_rate()

    @property
    def mob_usd_rate(self):
        if not self._mob_usd_rate or (self._last_checked + self._rate_ttl) < datetime.datetime.utcnow().timestamp():
            PriceAPI.logger.info("Getting new rate for MOB/USD...")
            self._mob_usd_rate = self.last_mob_to_usd_rate()
            PriceAPI.logger.info(f"MOB/USD rate: {self._mob_usd_rate}")
        return self._mob_usd_rate

    def last_mob_to_usd_rate(self) -> float:
        result = PriceAPI._get_url(f"{self.BASE_FTX_API}/markets/MOB/USD")
        if result['success']:
            return float(result['result']['last'])
        else:
            return 0.0

    def picomob_to_gbp(self, amt_picomob: int) -> float:
        amt_mob = amt_picomob/(10**12)
        return self.mob_usd_rate * amt_mob * self.usd_gbp_rate

