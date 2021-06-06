from django.db import models
from typing import TypeVar, Any
from dataclasses import dataclass


@dataclass
class ChangedField:
    field_name: str
    old_value: Any
    new_value: Any
    

T = TypeVar('T', bound=models.Model)
S = TypeVar('S', bound=models.Model)
V = TypeVar('V', bound=models.Model)



