class ModelUnavailable(Exception):
    def __init__(self, message="The model is unavailable.", sent=None):
        super().__init__(message)
        self.sent = sent


class ModelReply:
    def __init__(self, text: str, model: str, sent=None, message=None):
        self.text = text
        self.model = model
        self.sent = sent
        self.message = message


class ChatModel:
    def reply(self, messages: list[dict], format=None, options=None) -> ModelReply:
        raise NotImplementedError
