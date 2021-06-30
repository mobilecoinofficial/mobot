import os
import json
import random
import re
import socket
from typing import Iterator, List  # noqa

from .types import Attachment, Message

# We'll need to know the compiled RE object later.
RE_TYPE = type(re.compile(""))

def readlines(s: socket.socket) -> Iterator[bytes]:
    "Read a socket, line by line."
    buf = []  # type: List[bytes]
    while True:
        char = s.recv(1)
        if not char:
            raise ConnectionResetError("connection was reset")

        if char == b"\n":
            yield b"".join(buf)
            buf = []
        else:
            buf.append(char)


class Signal:
    def __init__(self, username, socket_path="/var/run/signald/signald.sock"):
        self.username = username
        self.socket_path = socket_path
        self._chat_handlers = []
        self._payment_handlers = []
        print("Connecting to signald at {}".format(socket_path))

    def _get_id(self):
        "Generate a random ID."
        return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))

    def _get_socket(self) -> socket.socket:
        "Create a socket, connect to the server and return it."

        # Support TCP sockets on the sly.
        if isinstance(self.socket_path, tuple):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.socket_path)
        return s

    def _send_command(self, payload: dict, block: bool = False):
        s = self._get_socket()
        msg_id = self._get_id()
        payload["id"] = msg_id
        s.recv(1024)  # Flush the buffer.
        s.send(json.dumps(payload).encode("utf8") + b"\n")

        if not block:
            return

        response = s.recv(4 * 1024)
        for line in response.split(b"\n"):
            if msg_id.encode("utf8") not in line:
                continue

            data = json.loads(line)

            if data.get("id") != msg_id:
                continue

            if data["type"] == "unexpected_error":
                raise ValueError("unexpected error occurred")

        return response

    def register(self, voice=False):
        """
        Register the given number.

        voice: Whether to receive a voice call or an SMS for verification.
        """
        payload = {"type": "register", "username": self.username, "voice": voice}
        self._send_command(payload)

    def verify(self, code: str):
        """
        Verify the given number by entering the code you received.

        code: The code Signal sent you.
        """
        payload = {"type": "verify", "username": self.username, "code": code}
        self._send_command(payload)

    def receive_messages(self) -> Iterator[Message]:
        "Keep returning received messages."
        s = self._get_socket()
        s.send(json.dumps({"type": "subscribe", "username": self.username}).encode("utf8") + b"\n")
        for line in readlines(s):
            try:
                message = json.loads(line.decode())
            except json.JSONDecodeError:
                print("Invalid JSON")

            if message.get("type") == "unreadable_message":
                self.send_message(message["data"]["source"], "Could you repeat that?")

            if message.get("type") != "message" or (
                not message["data"].get("isReceipt") and message["data"].get("dataMessage") is None
            ):
                # We need to do more digging to figure out what all of the other message types could
                # be, and how to properly handle them when they occur
                continue

            message = message["data"]
            data_message = message.get("dataMessage", {})

            yield Message(
                username=message["username"],
                source=message["source"],
                text=data_message.get("body"),
                source_device=message["sourceDevice"],
                timestamp=data_message.get("timestamp"),
                timestamp_iso=message["timestampISO"],
                expiration_secs=data_message.get("expiresInSeconds"),
                is_receipt=message.get("isReceipt"),
                group_info=data_message.get("groupInfo", {}),
                payment=data_message.get("payment", None)
            )

    def send_attachment(self, recipient, attachmentFilename, message, block: bool = True) -> None:
        """
        Send a message.

        recipient: The recipient's phone number, in E.123 format.
        attachmentFilename: The attachment's filename. Does not include directory path.
        block:     Whether to block while sending. If you choose not to block, you won't get an exception if there
                   are any errors.
        """
        payload = {
            "type": "send",
            "username": self.username,
            "recipientAddress": recipient,
            "messageBody": message,
            # The attachment file has to be located in the signald_data/ directory.
            # When it gets mounted as a volume on Docker, the directory becomes signald/.
            "attachments":[{'filename': '/signald/' + attachmentFilename}]
        }
        self._send_command(payload, block)

    def send_message(self, recipient, text: str, block: bool = True) -> None:
        """
        Send a message.

        recipient: The recipient's phone number, in E.123 format.
        text:      The text of the message to send.
        block:     Whether to block while sending. If you choose not to block, you won't get an exception if there
                   are any errors.
        """
        payload = {"type": "send", "username": self.username, "recipientAddress": recipient, "messageBody": text}
        self._send_command(payload, block)


    def send_receipt(self, recipient, timestamps, block: bool = True) -> None:
        if not isinstance(timestamps, list):
            timestamps = [timestamps]

        payload = {
            "type": "mark_read",
            "username": self.username,
            "recipientAddress": recipient,
            "timestamps": timestamps
        }
        self._send_command(payload, block)


    def send_group_message(self, recipient_group_id: str, text: str, block: bool = False) -> None:
        """
        Send a group message.

        recipient_group_id: The base64 encoded group ID to send to.
        text:               The text of the message to send.
        block:              Whether to block while sending. If you choose not to block, you won't get an exception if
                            there are any errors.
        """
        payload = {
            "type": "send",
            "username": self.username,
            "recipientGroupId": recipient_group_id,
            "messageBody": text,
        }
        self._send_command(payload, block)


    def send_payment_receipt(self, recipient_address: str, receiver_receipt: dict, message: str, block: bool = True) -> None:
        """
        Sends a payment receipt. Make sure to only call this method once we've verified that the transaction landed.

        Note: These fields correspond to the com.mobilecoin.api.Receipt proto. See the Android SDK for this definition.

        recipient_address: The Signal address for the recipient of this payment receipt.
        receiver_receipt: The payment reciept. Check out https://github.com/mobilecoinofficial/full-service/blob/58c411eedb349c9cb85e78178afe9e1bebd9e2cb/API.md#transaction-receipts
        """
        payload = {
            "type": "send",
            # Needs to be v1 because v0 doesn't parse payment.
            "version": "v1",
            "username": self.username,
            "recipientAddress": recipient_address,
            "payment": {
                "txo_public_key": receiver_receipt["public_key"],
                "txo_confirmation": receiver_receipt["confirmation"],
                "tombstone": receiver_receipt["tombstone_block"],
                "amount_commitment": receiver_receipt["amount"]["commitment"],
                "amount_masked": receiver_receipt["amount"]["masked_value"]
            }
        }
        print("---------receipt payload-----------")
        print(payload)
        self._send_command(payload, block)

    """
        avatar_filename: The filename for the avatar image you wish to set. It
        should be located in the signald_data directory.
    """
    # TODO: Make public_address a required argument.
    def set_profile(self, display_name, public_address=None, avatar_filename=None, block: bool = True):
        payload = {
            "type": "set_profile",
            "version": "v1",
            "account": self.username,
            "name": display_name,
        }
        if public_address:
            payload.update(paymentsAddress=public_address)
        if avatar_filename:
            payload.update(avatarFile=f"/signald/{avatar_filename}")

        self._send_command(payload, block)


    def get_profile(self, recipient, block: bool = True):
        payload = {
            "type": "get_profile",
            "username": self.username,
            "recipientAddress": recipient,
        }
        response = self._send_command(payload, block)
        as_string = response.decode('utf8')
        data = json.loads(as_string)

        return data

    def get_profile_from_phone_number(self, phone_number):
        recipient = {
            "number": phone_number
        }

        return self.get_profile(recipient)


    def chat_handler(self, regex, order=100):
        """
        A decorator that registers a chat handler function with a regex.
        """
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)

        def decorator(func):
            self._chat_handlers.append((order, regex, func))
            # Use only the first value to sort so that declaration order doesn't change.
            self._chat_handlers.sort(key=lambda x: x[0])
            return func

        return decorator

    def payment_handler(self, func):
        self._payment_handlers.append(func)
        return func

    def run_chat(self, auto_send_receipts=False):
        """
        Start the chat event loop.
        """
        for message in self.receive_messages():
            print(message)

            if message.payment:
                for func in self._payment_handlers:
                    func(message.source, message.payment)
                continue

            if not message.text:
                continue

            for _, regex, func in self._chat_handlers:
                match = re.search(regex, message.text)
                if not match:
                    continue

                try:
                    reply = func(message, match)
                except Exception as e:  # noqa - We don't care why this failed.
                    print(e)
                    continue

                if isinstance(reply, tuple):
                    stop, reply = reply
                else:
                    stop = True


                # In case a message came from a group chat
                group_id = message.group_info.get("groupId")

                # mark read and get that sweet filled checkbox
                try:
                    if auto_send_receipts and not group_id:
                        self.send_receipt(recipient=message.source, timestamps=[message.timestamp])

                    if group_id:
                        self.send_group_message(recipient_group_id=group_id, text=reply)
                    else:
                        self.send_message(recipient=message.source, text=reply)
                except Exception as e:
                    print(e)

                if stop:
                    # We don't want to continue matching things.
                    break
