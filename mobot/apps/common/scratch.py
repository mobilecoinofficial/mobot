from datetime import datetime


class User:
    def __init__(self, country, payments):
        self.country = country
        self.has_payments = payments


class Drop:
    def __init__(self, validators):
        self.validators = validators

    def users_included(self, users):
        for u in users:
            if all(v(self, u) for v in self.validators ):
                yield u
# Validator functions.

def from_country(country):
    def v(drop, user):
        return user.country == country
    return v


all_users = [
    User('US', payments=True),
    User('UK', payments=True),
    User('UK', payments=False),
]
drop_1 = Drop([
    from_country('UK'),
    # max_users(50),
    # expires(datetime(2021, 6, 15, 0, 0, 0)),
    # total_mob(100),
])
print(list(drop_1.users_included(all_users)))