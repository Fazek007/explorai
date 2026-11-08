class ModelUnavailable(Exception):
    pass


class ModelReply:
    def __init__(self, text: str, model: str):
        self.text = text
        self.model = model


class ChatModel:
    def reply(self, messages: list[dict]) -> ModelReply:
        raise NotImplementedError
