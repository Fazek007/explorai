import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from chat.llm.base import ModelReply, ModelUnavailable


class OllamaModel:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model

    def reply(self, messages: list[dict]) -> ModelReply:
        payload = {
            "model": self.model_name,
            "stream": False,
            "messages": [
                {"role": message["role"], "content": message["text"]}
                for message in messages
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode())
            message = body["message"]
            content = message["content"]
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise ModelUnavailable("The model is unavailable.", sent=payload) from exc
        if not isinstance(content, str):
            raise ModelUnavailable("The model is unavailable.", sent=payload)
        return ModelReply(
            text=content,
            model=self.model_name,
            sent=payload,
            message=message,
        )
