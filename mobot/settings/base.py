import logging

from .common import *
import mobilecoin as fullservice


# False if not in os.environ
DEBUG = runtime_env('DEBUG')
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(LOG_LEVEL)

# Raises django's ImproperlyConfigured exception if SECRET_KEY not in os.environ
SECRET_KEY = runtime_env('SECRET_KEY')
STORE_NUMBER = runtime_env('STORE_NUMBER')
SIGNALD_ADDRESS = runtime_env('SIGNALD_ADDRESS')
SIGNALD_PORT = runtime_env('SIGNALD_PORT')
FULLSERVICE_ADDRESS = runtime_env('FULLSERVICE_ADDRESS')
FULLSERVICE_PORT = runtime_env('FULLSERVICE_PORT')
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
PHONENUMBER_DB_FORMAT = "E164"

FEE_PMOB = None
ACCOUNT_ID = None
STORE_ADDRESS = None

fs_client = fullservice.Client(FULLSERVICE_URL)

try:
    accounts_map = fs_client.get_all_accounts()
    account_id = next(iter(accounts_map))
    account_obj = accounts_map[account_id]
    STORE_ADDRESS = account_obj['main_address']
    ACCOUNT_ID = account_obj['account_id']
except Exception as e:
    print("Failed to get full service account ID or")
    raise e

try:
    network_status_response = fs_client.get_network_status()
    FEE_PMOB = int(network_status_response['fee_pmob'])
except Exception as e:
    print("Failed to get network status response")
    raise e

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {
    # read os.environ['DATABASE_URL'] and raises ImproperlyConfigured exception if not found
    'default': runtime_env.db(),
    # read os.environ['SQLITE_URL']
    'extra': runtime_env.db('SQLITE_URL', default='sqlite:////tmp/my-tmp-sqlite.db')
}