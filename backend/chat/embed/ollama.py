import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from chat.embed.base import EmbedderUnavailable


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed([f"search_document: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([f"search_query: {text}"])
        return vectors[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        payload = {"model": self.model_name, "input": inputs}
        request = Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode())
            embeddings = body["embeddings"]
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise EmbedderUnavailable("The model is unavailable.") from exc
        if not self._is_embeddings(embeddings) or len(embeddings) != len(inputs):
            raise EmbedderUnavailable("The model is unavailable.")
        return embeddings

    def _is_embeddings(self, value) -> bool:
        if not isinstance(value, list) or not value:
            return False
        return all(
            isinstance(vector, list)
            and vector
            and all(isinstance(number, (int, float)) for number in vector)
            for vector in value
        )
