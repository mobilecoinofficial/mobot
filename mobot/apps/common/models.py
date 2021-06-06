from django.db import models
from typing import TypeVar, Generic, Dict, Any
from django.db.models.signals import pre_save, post_save, post_delete, post_init
from dataclasses import dataclass


@dataclass
class ChangedField:
    field_name: str
    old_value: Any
    new_value: Any


# class BaseMCModel(models.Model):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.changed: Dict[str, ChangedField]
#
#     def save(self, *args, **kwargs):
#         if self.pk:
#             # If self.pk is not None then it's an update.
#             cls = self.__class__
#             old = cls.objects.get(pk=self.pk)
#             # This will get the current model state since super().save() isn't called yet.
#             new = self  # This gets the newly instantiated Mode object with the new values.
#             changed_fields = []
#             for field in cls._meta.get_fields():
#                 field_name = field.name
#                 try:
#                     if getattr(old, field_name) != getattr(new, field_name):
#                         changed_fields.append(field_name)
#                 except Exception as ex:  # Catch field does not exist exception
#                     pass
#             kwargs['update_fields'] = changed_fields
#         super().save(*args, **kwargs)
#
#
#     def changed_fields(self) -> Dict[str, ChangedField]:


class BaseMCModel(models.Model):
    pass


T = TypeVar('T', bound=BaseMCModel)
S = TypeVar('S', bound=BaseMCModel)
V = TypeVar('V', bound=BaseMCModel)



