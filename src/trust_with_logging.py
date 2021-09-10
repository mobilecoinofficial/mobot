# coding: utf-8
import sys
import json

from signald_client import Signal


MOBOT = "+447401150900"
def trust_with_logging(signal):
    all_identities_response = signal.get_all_identities()
    identity_keys = all_identities_response["data"]["identity_keys"]
    for identity_key in identity_keys:
        identities = identity_key["identities"]
        for identity in identities:
            if identity["trust_level"] == "UNTRUSTED" or identity["trust_level"] == "TRUSTED_UNVERIFIED":
                number = identity_key["address"]["number"]
                print(f"Attempting to trust user {number}")
                try:
                    signal.trust(identity_key["address"]["number"], identity["safety_number"], True)
                except Exception as e:
                    print(f"Got an exception while trusting user {number}")


if __name__ == "__main__":
    number = sys.argv[1]

    print(f"Running Trust_all_untrusted for number {number}")
    signal = Signal(number, ("127.0.0.1", 15432))
    trust_with_logging(signal)
