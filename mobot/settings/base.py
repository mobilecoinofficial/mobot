from .common import *



# False if not in os.environ
DEBUG = runtime_env('DEBUG')

# Raises django's ImproperlyConfigured exception if SECRET_KEY not in os.environ
SECRET_KEY = runtime_env('SECRET_KEY')
STORE_ADDRESS = runtime_env('STORE_ADDRESS')
STORE_NUMBER = runtime_env('STORE_NUMBER')
SIGNALD_ADDRESS = runtime_env('SIGNALD_ADDRESS')
SIGNALD_PORT = runtime_env('SIGNALD_PORT')
ACCOUNT_ID = runtime_env('ACCOUNT_ID')
FULLSERVICE_ADDRESS = runtime_env('FULLSERVICE_ADDRESS')
FULLSERVICE_PORT = runtime_env('FULLSERVICE_PORT')
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
PHONENUMBER_DB_FORMAT = "E164"


# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {
    # read os.environ['DATABASE_URL'] and raises ImproperlyConfigured exception if not found
    'default': runtime_env.db(),
    # read os.environ['SQLITE_URL']
    'extra': runtime_env.db('SQLITE_URL', default='sqlite:////tmp/my-tmp-sqlite.db')
}

CACHES = {
    # read os.environ['CACHE_URL'] and raises ImproperlyConfigured exception if not found
    'default': runtime_env.cache(),
    # read os.environ['REDIS_URL']
    'redis': runtime_env.cache('REDIS_URL')
}

if __name__ == "__main__":
    print(SECRET_KEY)