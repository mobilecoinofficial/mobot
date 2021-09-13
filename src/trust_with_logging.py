# coding: utf-8
import sys
import json

from signald_client import Signal


class DebugSignal(Signal):

    def _send_command(self, payload: dict, block: bool = False):
        print(f"Sending command: {payload}")
        s = self._get_socket()
        msg_id = self._get_id()
        payload["id"] = msg_id
        s.recv(1024)  # Flush the buffer.
        s.send(json.dumps(payload).encode("utf8") + b"\n")

        if not block:
            return

        response_data = {}
        response = s.recv(4 * 1024)
        for line in response.split(b"\n"):
            if msg_id.encode("utf8") not in line:
                continue
            try:
                data = json.loads(line)

                if data.get("id") != msg_id:
                    continue

                if data["type"] == "unexpected_error":
                    raise ValueError("unexpected error occurred")

                if data.get("error_type") == "RequestValidationFailure":
                    raise ValueError(data.get("error"))

                response_data = data
            except json.decoder.JSONDecodeError as e:
                print(f"Got a bad JSON response: {line}")

        return response_data

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
