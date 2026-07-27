class HikvisionError(RuntimeError):
    """Base exception raised by the Hikvision infrastructure adapter."""


class HikvisionAuthenticationError(HikvisionError):
    pass


class HikvisionProtocolError(HikvisionError):
    pass


class HikvisionEventParseError(HikvisionProtocolError):
    pass
