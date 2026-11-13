from chat.llm import get_chat_model
from chat.llm.base import ModelUnavailable

CLASSIFIER = (
    "Reply with chat if the message is only a greeting, thanks, a farewell, "
    "or small talk. Reply with question otherwise. One word."
)


class Route:
    def __init__(self, decision, sent, received):
        self.decision = decision
        self.sent = sent
        self.received = received


def route(text: str) -> Route:
    messages = [
        {"role": "system", "text": CLASSIFIER},
        {"role": "user", "text": text},
    ]
    try:
        reply = get_chat_model().reply(messages)
    except ModelUnavailable as exc:
        return Route(decision="question", sent=exc.sent, received=None)
    word = ""
    if reply.text.strip():
        word = reply.text.strip().split()[0].strip(".,!?:;").lower()
    decision = "chat" if word == "chat" else "question"
    return Route(decision=decision, sent=reply.sent, received=reply.message)
