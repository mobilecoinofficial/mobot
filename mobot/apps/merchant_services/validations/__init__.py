from typing import Generic, Callable

from mobot.apps.merchant_services.validations import T, V
from mobot.apps.merchant_services.validations.validations import T, V


class OneModelValidation(Generic[T]):

    def __init__(self, validator: Callable[[T], bool]):
        self.validator = validator

    def validate(self, arg: T) -> bool:
        return self.validator(arg)


class TwoModelValidation(Generic[T, V]):
    def __init__(self, validator: Callable[[T, V], bool]):
        self.validator = validator

    def validate(self, arg1: T, arg2: V) -> bool:
        return self.validator(arg1, arg2)