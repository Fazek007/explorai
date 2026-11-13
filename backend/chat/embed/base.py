class EmbedderUnavailable(Exception):
    pass


class Embedder:
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError
