import re


def split_paragraphs(text: str, source: str) -> list[dict]:
    paragraphs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        cleaned = block.strip()
        if not cleaned:
            continue
        paragraphs.append(
            {
                "source": source,
                "position": len(paragraphs),
                "text": cleaned,
            }
        )
    return paragraphs
