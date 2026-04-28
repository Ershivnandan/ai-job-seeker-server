from app.config import settings
from app.services.llm.base import BaseLLMProvider


def get_llm_provider() -> BaseLLMProvider:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider == "anthropic":
        from app.services.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider == "ollama":
        from app.services.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'openai', 'anthropic', or 'ollama'.")
