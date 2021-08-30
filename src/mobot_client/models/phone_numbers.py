#  Copyright (c) 2021 MobileCoin. All rights reserved.

#  Copyright (c) 2021 MobileCoin. All rights reserved.
from phonenumbers import PhoneNumber
from phonenumber_field.modelfields import PhoneNumberField as BasePhoneNumberField


class PhoneNumberWithRFC3966(PhoneNumber):
    @property
    def country_code_string(self) -> str:
        return f"+{self.country_code}"

    def __str__(self) -> str:
        return self.as_e164


class PhoneNumberField(BasePhoneNumberField):
    attr_class = PhoneNumberWithRFC3966

    def get_internal_type(self):
        return "TextField"