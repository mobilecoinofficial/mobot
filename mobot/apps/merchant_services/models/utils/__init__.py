import dataclasses
from typing import Any, Dict, List, Tuple, Type, TypeVar, Union

from django.contrib.postgres.fields import JSONField
from django.db.models import F, Func, Value

T = TypeVar("T")


class DataclassField(JSONField):
    """
    A field that stores dataclasses in a jsonb field in the database.
    """

    def __init__(self, dataclass, null=False):

        # Make sure a dataclass was given
        assert dataclasses.is_dataclass(dataclass)

        super().__init__(null=null)

        self.dataclass = dataclass

    def to_python(self, value):

        if isinstance(value, self.dataclass):
            return value

        if value is None:
            return None

        return _class_from_dict(dataclass=self.dataclass, value=value)

    def from_db_value(self, value, expression, connection):
        if not value:
            return None

        return _class_from_dict(dataclass=self.dataclass, value=value)

    def get_prep_value(self, value):

        return super().get_prep_value(
            dataclasses.asdict(value) if value is not None else None
        )

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["dataclass"] = self.dataclass
        return name, path, args, kwargs


class JSONObject(Func):
    """
    Create JSON objects from rows in the database.
    """

    # pylint: disable=abstract-method
    function = "jsonb_build_object"

    def __init__(self, *args: str, output_field=None, **kwargs: Union[Value, F]):

        key_value_pairs: List[Tuple[Value, Union[Value, F]]] = []
        key_value_pairs.extend((Value(key), key) for key in args)
        key_value_pairs.extend((Value(key), value) for key, value in kwargs.items())

        super().__init__(
            *[item for pair in key_value_pairs for item in pair],
            output_field=output_field or JSONField()
        )


def _class_from_dict(*, dataclass: Type[T], value: Dict[str, Any]) -> T:
    """
    Super simple helper to initialize a dataclass from the given value. Also
    handles nested dataclasses, but not more complex types like lists or sets.
    """

    kwargs = {
        field.name: (
            _class_from_dict(dataclass=field.type, value=value[field.name])
            if dataclasses.is_dataclass(field.type)
            else value[field.name]
        )
        for field in dataclasses.fields(dataclass)
    }

    return dataclass(**kwargs)