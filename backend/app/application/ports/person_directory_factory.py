from abc import ABC, abstractmethod

from app.application.ports.person_directory import PersonDirectory
from app.domain.entities.device import Device


class PersonDirectoryFactory(ABC):
    @abstractmethod
    def create(self, device: Device) -> PersonDirectory:
        raise NotImplementedError
