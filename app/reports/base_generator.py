from abc import ABC, abstractmethod
from typing import Any


class ReportGenerator(ABC):
    """Abstract base class for report generation strategies."""

    @abstractmethod
    def generate(self, data: dict) -> bytes:
        """Generate a report from the provided data payload."""
        raise NotImplementedError
