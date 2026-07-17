"""Base class for entropy sources."""

from abc import ABC, abstractmethod
from typing import Any, List


" Abstract base class for a source that produces raw entropy data"
class EntropySource(ABC):

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_raw(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def standardize(self, raw: Any) -> List[int]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "EntropySource":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()