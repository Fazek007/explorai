import math

from django.conf import settings

from chat.embed import get_embedder
from chat.models import Chunk


class Hit:
    def __init__(self, chunk: Chunk, score: float):
        self.chunk = chunk
        self.score = score


def cosine(left: list[float], right: list[float]) -> float:
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


def retrieve(question: str) -> list[Hit]:
    embedder = get_embedder()
    query = embedder.embed_query(question)
    hits = []
    for chunk in Chunk.objects.filter(embed_model=embedder.model_name):
        score = cosine(query, chunk.embedding)
        if score >= settings.RAG_MIN_SCORE:
            hits.append(Hit(chunk=chunk, score=score))
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[: settings.RAG_TOP_K]
