from pathlib import Path

from django.db import transaction

from chat.embed import get_embedder
from chat.models import Chunk
from chat.rag.chunking import split_paragraphs


def index_directory(directory: Path) -> list[tuple[str, int]]:
    embedder = get_embedder()
    indexed = []
    for path in sorted(Path(directory).glob("*.md")):
        paragraphs = split_paragraphs(path.read_text(), path.name)
        vectors = embedder.embed_documents([item["text"] for item in paragraphs])
        with transaction.atomic():
            Chunk.objects.filter(source=path.name).delete()
            Chunk.objects.bulk_create(
                [
                    Chunk(
                        source=item["source"],
                        position=item["position"],
                        text=item["text"],
                        embedding=vector,
                        embed_model=embedder.model_name,
                    )
                    for item, vector in zip(paragraphs, vectors)
                ]
            )
        indexed.append((path.name, len(paragraphs)))
    return indexed
