import json
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    async def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def complete_json(self, messages: list[dict], temperature: float = 0.1) -> dict[str, Any]:
        messages = [*messages]
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += "\n\nYou MUST respond with valid JSON only. No markdown, no code fences."
        else:
            messages.insert(0, {
                "role": "system",
                "content": "You MUST respond with valid JSON only. No markdown, no code fences.",
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
