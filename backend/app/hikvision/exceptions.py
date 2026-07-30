class HikvisionError(RuntimeError):
    """Base exception raised by the Hikvision infrastructure adapter."""


class HikvisionAuthenticationError(HikvisionError):
    pass


class HikvisionProtocolError(HikvisionError):
    pass


class HikvisionEventParseError(HikvisionProtocolError):
    pass


class HikvisionResourceMissing(HikvisionProtocolError):
    """The device answered that what was asked for is not there.

    Distinct from a failure: a face enrolled from the biometric template alone has
    no picture stored, and the device says so with a 404.
    """
