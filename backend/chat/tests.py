from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from chat.llm.base import ModelReply, ModelUnavailable
from chat.models import GREETING, Conversation, Message


class FakeModel:
    def __init__(self):
        self.calls = []

    def reply(self, messages):
        self.calls.append(messages)
        return ModelReply(text="The water is calm.", model="fake-model")


class FailingModel:
    def reply(self, messages):
        raise ModelUnavailable("down")


class ConversationApiTests(TestCase):
    def test_new_conversation_starts_with_the_greeting(self):
        response = self.client.post(reverse("conversations"))

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "assistant")
        self.assertEqual(payload["messages"][0]["text"], GREETING)
        self.assertEqual(payload["messages"][0]["model"], "")
        self.assertEqual(payload["messages"][0]["sources"], [])

    def test_sent_message_stores_the_reply(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        fake = FakeModel()

        with patch("chat.views.get_chat_model", return_value=fake):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "How is the lake?"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "text": "The water is calm.",
                "model": "fake-model",
                "sources": [],
            },
        )
        stored = list(
            Message.objects.filter(conversation_id=conversation_id).values_list(
                "role", "text", "model"
            )
        )
        self.assertEqual(
            stored,
            [
                ("assistant", GREETING, ""),
                ("user", "How is the lake?", ""),
                ("assistant", "The water is calm.", "fake-model"),
            ],
        )
        self.assertEqual(fake.calls[0][-1], {"role": "user", "text": "How is the lake?"})

    def test_model_failure_keeps_the_user_message(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]

        with patch("chat.views.get_chat_model", return_value=FailingModel()):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "Hello"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "The model is unavailable."})
        self.assertTrue(
            Message.objects.filter(
                conversation_id=conversation_id,
                role="user",
                text="Hello",
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                conversation_id=conversation_id,
                role="assistant",
                text="The model is unavailable.",
            ).exists()
        )

    def test_wipe_removes_every_conversation(self):
        self.client.post(reverse("conversations"))
        self.client.post(reverse("conversations"))

        response = self.client.delete(reverse("conversations"))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
