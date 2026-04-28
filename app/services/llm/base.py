from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        """Send messages and return the text response."""
        ...

    @abstractmethod
    async def complete_json(self, messages: list[dict], temperature: float = 0.1) -> dict[str, Any]:
        """Send messages and return a parsed JSON response."""
        ...
