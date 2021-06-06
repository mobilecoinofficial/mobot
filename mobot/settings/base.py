from .common import *
import mobilecoin as fullservice


# False if not in os.environ
DEBUG = runtime_env('DEBUG')

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

try:
    fullservice_client = fullservice.Client(FULLSERVICE_URL)
    accounts_map = fullservice_client.get_all_accounts()
    account_id = next(iter(accounts_map))
    account_obj = accounts_map[account_id]
    network_status_response = fullservice_client.get_network_status()
    STORE_ADDRESS = account_obj['main_address']
    ACCOUNT_ID = account_obj['account_id']
    FEE_PMOB = int(network_status_response['fee_pmob'])
except Exception as e:
    print("Failed to get full service account ID")
    raise e

print(f"FULLSERVICE_ACCOUNT: {ACCOUNT_ID}")

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {
    # read os.environ['DATABASE_URL'] and raises ImproperlyConfigured exception if not found
    'default': runtime_env.db(),
    # read os.environ['SQLITE_URL']
    'extra': runtime_env.db('SQLITE_URL', default='sqlite:////tmp/my-tmp-sqlite.db')
}


if __name__ == "__main__":
    print(SECRET_KEY)