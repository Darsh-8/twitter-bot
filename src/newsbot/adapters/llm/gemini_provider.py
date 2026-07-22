from newsbot.adapters.llm.openai_compatible_provider import OpenAICompatibleJSONProvider

# Google AI Studio's OpenAI-compatible endpoint (free tier, generated via aistudio.google.com/apikey).
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiLLMProvider(OpenAICompatibleJSONProvider):
    provider_label = "Gemini"

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model, base_url=GEMINI_BASE_URL)
