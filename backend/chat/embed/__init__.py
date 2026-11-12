from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from chat.embed.ollama import OllamaEmbedder


def get_embedder():
    provider = settings.EMBED_PROVIDER
    if provider == "ollama":
        return OllamaEmbedder(settings.OLLAMA_BASE_URL, settings.OLLAMA_EMBED_MODEL)
    raise ImproperlyConfigured(f"Unknown EMBED_PROVIDER: {provider}")
