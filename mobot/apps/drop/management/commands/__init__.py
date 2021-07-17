import os
import sys
from mobot.apps.merchant_services.models import Campaign, Product, ProductGroup, MobotStore, Merchant, Order, InventoryItem, Validation, Customer
from mobot.campaigns.hoodies import Size
from mobot.lib.currency import MOB, PMOB

sys.path.append("/app/")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mobot.settings")
