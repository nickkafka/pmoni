import asyncio
from typing import Generic, TypeVar

from app.core.logger import logger

T = TypeVar("T")


class EventBroadcaster(Generic[T]):
    """Fans out events to independent subscriber queues.

    A queue that reaches its limit loses its oldest event, so a slow consumer never
    blocks delivery to the others nor holds back the device supervisors.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[T]] = set()

    def subscribe(self, *, max_queue_size: int = 100) -> asyncio.Queue[T]:
        if max_queue_size <= 0:
            raise ValueError("O tamanho da fila deve ser maior que zero.")
        queue: asyncio.Queue[T] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[T]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: T) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                logger.warning("Fila de eventos cheia; evento antigo descartado.")
            queue.put_nowait(event)
