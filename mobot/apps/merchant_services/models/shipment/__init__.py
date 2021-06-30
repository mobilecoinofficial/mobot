from enum import Enum

from address.models import AddressField, Address
from django.db import models
from django_fsm import FSMIntegerField, transition
from mobot.apps.common.models import Trackable

