from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Device:
    """Equipment registered as an access-control event source."""

    id: int | None
    name: str
    host: str
    port: int
    username: str
    model: str | None
    enabled: bool
