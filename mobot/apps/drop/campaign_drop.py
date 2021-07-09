import logging
import sys
import os
from typing import Optional

from mobot.apps.merchant_services.models import Campaign, Customer, DropSession

sys.path.append("/app/")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


class Drop:
    def __init__(self, campaign: Campaign):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.campaign = campaign
        self.store = campaign.store

    def _find_current_session(self, customer: Customer) -> Optional[DropSession]:
        try:
            session = DropSession.objects.get(customer=customer)
            return session
        except Customer.DoesNotExist:
            self.logger.exception(f"Session for {customer} doesn't exist yet")

    def _register_new_customer(self, customer: Customer):
        """We hear from a new customer and register them."""