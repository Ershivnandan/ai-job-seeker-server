import json
from typing import Any

import httpx

from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = "gemma3:4b"

    async def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def complete_json(self, messages: list[dict], temperature: float = 0.1) -> dict[str, Any]:
        messages = [*messages]
        json_instruction = "\n\nYou MUST respond with valid JSON only. No markdown, no code fences, no explanation."

        if messages and messages[0]["role"] == "system":
            messages[0] = {**messages[0], "content": messages[0]["content"] + json_instruction}
        else:
            messages.insert(0, {"role": "system", "content": json_instruction.strip()})

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            return json.loads(content)
