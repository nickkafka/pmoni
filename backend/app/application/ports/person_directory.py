from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.entities.resident import EnrolledPerson


class PersonDirectory(ABC):
    """Read-only view of the people enrolled on one device."""

    @abstractmethod
    def list_enrolled(self) -> AsyncIterator[EnrolledPerson]:
        """Yield every enrolled person, without their photo."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_photo(self, reference: str) -> bytes | None:
        """Download one enrollment photo, or return ``None`` when it is gone."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
