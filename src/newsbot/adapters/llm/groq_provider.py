from newsbot.adapters.llm.openai_compatible_provider import OpenAICompatibleJSONProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMProvider(OpenAICompatibleJSONProvider):
    provider_label = "Groq"

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model, base_url=GROQ_BASE_URL)
