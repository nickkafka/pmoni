from collections import OrderedDict

from app.application.ports.snapshot_store import SnapshotStore


class InMemorySnapshotStore(SnapshotStore):
    """Keeps the most recent captures in memory, discarding the oldest.

    Captures are only useful while the passage is still on screen, so they are never
    persisted: a restart simply starts collecting again.
    """

    def __init__(self, *, capacity: int = 200) -> None:
        if capacity <= 0:
            raise ValueError("A capacidade deve ser maior que zero.")
        self._capacity = capacity
        self._images: OrderedDict[tuple[int, str], bytes] = OrderedDict()

    def put(self, device_id: int, external_id: str, image: bytes) -> None:
        key = (device_id, external_id)
        self._images.pop(key, None)
        self._images[key] = image
        while len(self._images) > self._capacity:
            self._images.popitem(last=False)

    def get(self, device_id: int, external_id: str) -> bytes | None:
        return self._images.get((device_id, external_id))
