from newsbot.adapters.llm.anthropic_provider import AnthropicLLMProvider
from newsbot.adapters.llm.gemini_provider import GeminiLLMProvider
from newsbot.adapters.llm.groq_provider import GroqLLMProvider
from newsbot.adapters.llm.openai_provider import OpenAILLMProvider
from newsbot.application.interfaces.llm_provider import LLMProvider
from newsbot.config.settings import Settings


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model_anthropic,
        )
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAILLMProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model_openai,
        )
    if settings.llm_provider == "groq":
        keys: list[str] = []
        if settings.groq_api_keys:
            keys = [k.strip() for k in settings.groq_api_keys.get_secret_value().split(",") if k.strip()]
        elif settings.groq_api_key:
            keys = [settings.groq_api_key.get_secret_value()]
        if not keys:
            raise RuntimeError("GROQ_API_KEY or GROQ_API_KEYS is required when LLM_PROVIDER=groq")
        return GroqLLMProvider(api_keys=keys, model=settings.llm_model_groq)
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.llm_model_gemini,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
