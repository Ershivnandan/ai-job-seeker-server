import json
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    async def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text

    async def complete_json(self, messages: list[dict], temperature: float = 0.1) -> dict[str, Any]:
        messages = [*messages]
        json_instruction = "\n\nYou MUST respond with valid JSON only. No markdown, no code fences, no explanation."

        if messages and messages[0]["role"] == "system":
            messages[0] = {**messages[0], "content": messages[0]["content"] + json_instruction}
        else:
            messages.insert(0, {"role": "system", "content": json_instruction.strip()})

        content = await self.complete(messages, temperature)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(content)
