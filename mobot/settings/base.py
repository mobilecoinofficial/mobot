from .common import *

import environ


# False if not in os.environ
DEBUG = env('DEBUG')

# Raises django's ImproperlyConfigured exception if SECRET_KEY not in os.environ
SECRET_KEY = env('SECRET_KEY')
STORE_ADDRESS = env('STORE_ADDRESS')
STORE_NUMBER = env('STORE_NUMBER')
SIGNALD_ADDRESS = env('SIGNALD_ADDRESS')
SIGNALD_PORT = env('SIGNALD_PORT')
FULLSERVICE_ADDRESS = env('FULLSERVICE_ADDRESS', "127.0.0.1")
FULLSERVICE_PORT = env('FULLSERVICE_PORT', "9090")
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
PHONENUMBER_DB_FORMAT = "E164"


# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {
    # read os.environ['DATABASE_URL'] and raises ImproperlyConfigured exception if not found
    'default': env.db(),
    # read os.environ['SQLITE_URL']
    'extra': env.db('SQLITE_URL', default='sqlite:////tmp/my-tmp-sqlite.db')
}

CACHES = {
    # read os.environ['CACHE_URL'] and raises ImproperlyConfigured exception if not found
    'default': env.cache(),
    # read os.environ['REDIS_URL']
    'redis': env.cache('REDIS_URL')
}

if __name__ == "__main__":
    print(SECRET_KEY)