from abc import ABC, abstractmethod
from typing import Mapping, Any


class AlertChannel(ABC):
    """Abstract base for all alert channels.

    Subclasses must implement `send(target, payload)` and return a boolean
    indicating success.
    """

    @abstractmethod
    def send(self, target: str, payload: Mapping[str, Any]) -> bool:
        """Send `payload` to the given `target`.

        Args:
            target: The destination identifier (e.g., channel name, ARN, URL).
            payload: The payload to send.

        Returns:
            True if the send succeeded, False otherwise.
        """
        raise NotImplementedError
