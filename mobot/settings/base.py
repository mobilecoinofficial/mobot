import logging

from .common import *
import mobilecoin as fullservice
from moneyed import add_currency

# False if not in os.environ
DEBUG = runtime_env('DEBUG')
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(level=LOG_LEVEL)

# Raises django's ImproperlyConfigured exception if SECRET_KEY not in os.environ
SECRET_KEY = runtime_env('SECRET_KEY')
STORE_NUMBER = runtime_env('STORE_NUMBER')
SIGNALD_ADDRESS = runtime_env('SIGNALD_ADDRESS')
SIGNALD_PORT = runtime_env('SIGNALD_PORT')
FULLSERVICE_ADDRESS = runtime_env('FULLSERVICE_ADDRESS')
FULLSERVICE_PORT = runtime_env('FULLSERVICE_PORT')
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
PHONENUMBER_DB_FORMAT = "E164"
EXCHANGE_BACKEND = 'mobot.apps.merchant_services.ftx.OpenExchangeRatesWithFtxBackend'
OPEN_EXCHANGE_RATES_APP_ID = runtime_env('OPEN_EXCHANGE_RATES_APP_ID')
USE_TZ = True
TEST = True

FEE_PMOB = None
ACCOUNT_ID = None
STORE_ADDRESS = None

fs_client = fullservice.Client(FULLSERVICE_URL)
if not TEST:
    try:
        print("Getting Fullservice client connection")
        accounts_map = fs_client.get_all_accounts()
        account_id = next(iter(accounts_map))
        account_obj = accounts_map[account_id]
        STORE_ADDRESS = account_obj['main_address']
        ACCOUNT_ID = account_obj['account_id']
    except Exception as e:
        print("Failed to get full service account ID")
        if not DEBUG:
            raise e


    try:
        network_status_response = fs_client.get_network_status()
        FEE_PMOB = int(network_status_response['fee_pmob'])
    except Exception as e:
        print("Failed to get network status response")
        if not DEBUG:
            raise e


EXCHANGE_BACKEND = 'mobot.apps.merchant_services.ftx.OpenExchangeRatesWithFtxBackend'

DEFAULT_TIME_IN_CART_SECS = 1200
REFRESH_TIME_IN_CART_SECS = 600

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
