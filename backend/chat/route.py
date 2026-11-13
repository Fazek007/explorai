import json

from chat.llm import get_chat_model
from chat.llm.base import ModelUnavailable

CLASSIFIER = (
    "Classify the latest user message, using the earlier lines only as context. "
    "route is question if the latest message asks anything, requests information "
    "or more detail, or continues the topic of the earlier assistant answer. "
    "route is chat only if it is a greeting, thanks, a farewell, a reaction, "
    "or a statement about the user."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "route": {"type": "string", "enum": ["chat", "question"]},
    },
    "required": ["route"],
}


class Route:
    def __init__(self, decision, sent, received):
        self.decision = decision
        self.sent = sent
        self.received = received


# The new message plus the 2 before it. The window stays this short for now
# so the small local models, the 8B classifier and nomic-embed-text, are not
# given a long chat history.
def recent_block(messages) -> str:
    chosen = list(messages)[-3:]
    lines = []
    for message in chosen:
        label = "Assistant" if message.role == "assistant" else "User"
        lines.append(f"{label}: {message.text}")
    return "\n".join(lines)


def route(block: str) -> Route:
    messages = [
        {"role": "system", "text": CLASSIFIER},
        {"role": "user", "text": block},
    ]
    try:
        reply = get_chat_model().reply(
            messages,
            format=SCHEMA,
            options={"temperature": 0},
        )
    except ModelUnavailable as exc:
        return Route(decision="question", sent=exc.sent, received=None)
    decision = "question"
    try:
        parsed = json.loads(reply.text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict) and parsed.get("route") == "chat":
        decision = "chat"
    return Route(decision=decision, sent=reply.sent, received=reply.message)
