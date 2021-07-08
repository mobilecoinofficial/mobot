import attr


@attr.s
class Attachment:
    content_type = attr.ib(type=str)
    id = attr.ib(type=str)
    size = attr.ib(type=int)
    stored_filename = attr.ib(type=str)


@attr.s
class Message:
    username = attr.ib(type=str)
    source = attr.ib(type=str)
    text = attr.ib(type=str)
    source_device = attr.ib(type=int, default=0)
    timestamp = attr.ib(type=int, default=None)
    timestamp_iso = attr.ib(type=str, default=None)
    expiration_secs = attr.ib(type=int, default=0)
    is_receipt = attr.ib(type=bool, default=False)
    attachments = attr.ib(type=list, default=[])
    quote = attr.ib(type=str, default=None)
    group_info = attr.ib(type=dict, default={})
    payment = attr.ib(type=dict, default={})
