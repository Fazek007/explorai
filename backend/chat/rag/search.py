import math

from django.conf import settings

from chat.embed import get_embedder
from chat.models import Chunk


class Hit:
    def __init__(self, chunk: Chunk, score: float):
        self.chunk = chunk
        self.score = score


class Retrieval:
    def __init__(self, hits: list[Hit], scored: list[dict]):
        self.hits = hits
        self.scored = scored


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


def retrieve(question: str) -> Retrieval:
    embedder = get_embedder()
    query = embedder.embed_query(question)
    ranked = []
    for chunk in Chunk.objects.filter(embed_model=embedder.model_name):
        ranked.append((chunk, cosine(query, chunk.embedding)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    hits = []
    kept_ids = set()
    for chunk, score in ranked:
        if score < settings.RAG_MIN_SCORE or len(hits) >= settings.RAG_TOP_K:
            continue
        hits.append(Hit(chunk=chunk, score=score))
        kept_ids.add(chunk.id)
    scored = [
        {
            "source": chunk.source,
            "position": chunk.position,
            "score": score,
            "kept": chunk.id in kept_ids,
        }
        for chunk, score in ranked
    ]
    return Retrieval(hits=hits, scored=scored)
