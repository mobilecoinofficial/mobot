import importlib

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


class ClassField(models.TextField):
    def to_python(self, value):
        if value is not None:
            module = importlib.import_module(".".join(value.split(".")[:-1]))
            cls_name = value.split(".")[-1]
            cls = getattr(module, cls_name)
            return cls

    def from_db_value(self, value, expression, connection, context=None):
        return self.to_python(value)

    def get_prep_value(self, value):
        return f"{value.__module__}.{value.__name__.lower()}"