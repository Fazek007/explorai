from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from chat.llm.ollama import OllamaModel


def get_chat_model():
    provider = settings.LLM_PROVIDER
    if provider == "ollama":
        return OllamaModel(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
    raise ImproperlyConfigured(f"Unknown LLM_PROVIDER: {provider}")
