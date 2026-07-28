from abc import ABC, abstractmethod


class SnapshotStore(ABC):
    """Holds the capture taken when a person walked through, for the interface to show.

    The images live only as long as they are worth displaying, so the store is a
    bounded cache rather than part of the resident record.
    """

    @abstractmethod
    def put(self, device_id: int, external_id: str, image: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, device_id: int, external_id: str) -> bytes | None:
        raise NotImplementedError
