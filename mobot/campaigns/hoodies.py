from dataclasses import dataclass
from dataclasses_json import dataclass_json
from enum import Enum
from django.db.models import QuerySet
from django.db import models

""" Still figuring out if this file is necessary """
class Size(str, Enum):
    S = "small"
    M = "medium"
    L = "large"
    XL = "extralarge"
    XXL = "extraextralarge"