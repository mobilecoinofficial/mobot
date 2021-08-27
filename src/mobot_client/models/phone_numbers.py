#  Copyright (c) 2021 MobileCoin. All rights reserved.

#  Copyright (c) 2021 MobileCoin. All rights reserved.
from phonenumbers import PhoneNumber
from phonenumber_field.modelfields import PhoneNumberField as BasePhoneNumberField


class PhoneNumberWithRFC3966(PhoneNumber):
    @property
    def country_code_string(self) -> str:
        return f"+{self.country_code}"

    @property
    def rfc3966(self) -> str:
        return f"+{self.country_code}{self.national_number}"

    def __str__(self) -> str:
        return f"+{self.country_code}{self.national_number}"


class PhoneNumberField(BasePhoneNumberField):
    attr_class = PhoneNumberWithRFC3966

    def get_internal_type(self):
        return "TextField"