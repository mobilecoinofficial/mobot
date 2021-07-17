import logging
from logging import Formatter


LOG_FORMAT = '%(asctime)s - %(module)s - %(name)s - %(levelname)s - %(message)s'

logging.basicConfig(format=LOG_FORMAT)

