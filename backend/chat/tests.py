import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.embed.base import EmbedderUnavailable
from chat.llm.base import ModelReply, ModelUnavailable
from chat.models import GREETING, Chunk, Conversation, Message
from chat.rag.chunking import split_paragraphs
from chat.rag.search import Hit, retrieve


class FakeModel:
    def __init__(self):
        self.calls = []

    def reply(self, messages):
        self.calls.append(messages)
        return ModelReply(text="The water is calm.", model="fake-model")


class FailingModel:
    def reply(self, messages):
        raise ModelUnavailable("down")


class FakeEmbedder:
    model_name = "fake-embed"

    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0]


class ConversationApiTests(TestCase):
    def setUp(self):
        super().setUp()
        patched = patch("chat.views.retrieve", return_value=[])
        patched.start()
        self.addCleanup(patched.stop)

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


class ChunkingTests(TestCase):
    def test_split_paragraphs_drops_empty_blocks_and_numbers_positions(self):
        text = "  First paragraph.  \n\n\n  Second paragraph.\nStill second.  \n\n   \n"

        paragraphs = split_paragraphs(text, "handbook.md")

        self.assertEqual(
            paragraphs,
            [
                {
                    "source": "handbook.md",
                    "position": 0,
                    "text": "First paragraph.",
                },
                {
                    "source": "handbook.md",
                    "position": 1,
                    "text": "Second paragraph.\nStill second.",
                },
            ],
        )


class IndexNotesTests(TestCase):
    def test_index_notes_writes_and_replaces_rows_for_one_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            note = path / "handbook.md"
            note.write_text("Alpha paragraph.\n\nBeta paragraph.\n")

            with patch("chat.rag.index.get_embedder", return_value=FakeEmbedder()):
                call_command("index_notes", dir=directory, stdout=StringIO())

            stored = list(
                Chunk.objects.filter(source="handbook.md").values_list(
                    "position", "text", "embed_model"
                )
            )
            self.assertEqual(
                stored,
                [
                    (0, "Alpha paragraph.", "fake-embed"),
                    (1, "Beta paragraph.", "fake-embed"),
                ],
            )
            self.assertEqual(
                Chunk.objects.get(source="handbook.md", position=0).embedding,
                [float(len("Alpha paragraph.")), 1.0],
            )

            note.write_text("Only paragraph.\n")
            with patch("chat.rag.index.get_embedder", return_value=FakeEmbedder()):
                call_command("index_notes", dir=directory, stdout=StringIO())

        self.assertEqual(
            list(
                Chunk.objects.filter(source="handbook.md").values_list(
                    "position", "text"
                )
            ),
            [(0, "Only paragraph.")],
        )


class QueryEmbedder:
    model_name = "fake-embed"

    def embed_query(self, text):
        return [1.0, 0.0]


@override_settings(RAG_TOP_K=2, RAG_MIN_SCORE=0.5)
class RetrieveTests(TestCase):
    def test_retrieve_ranks_limits_and_ignores_other_models(self):
        Chunk.objects.create(
            source="handbook.md",
            position=0,
            text="close",
            embedding=[1.0, 0.0],
            embed_model="fake-embed",
        )
        Chunk.objects.create(
            source="handbook.md",
            position=1,
            text="near",
            embedding=[0.8, 0.6],
            embed_model="fake-embed",
        )
        Chunk.objects.create(
            source="handbook.md",
            position=2,
            text="middle",
            embedding=[0.6, 0.8],
            embed_model="fake-embed",
        )
        Chunk.objects.create(
            source="handbook.md",
            position=3,
            text="far",
            embedding=[0.0, 1.0],
            embed_model="fake-embed",
        )
        Chunk.objects.create(
            source="other.md",
            position=0,
            text="other model",
            embedding=[1.0, 0.0],
            embed_model="other-embed",
        )

        with patch("chat.rag.search.get_embedder", return_value=QueryEmbedder()):
            hits = retrieve("when do the doors shut?")

        self.assertEqual([hit.chunk.text for hit in hits], ["close", "near"])
        self.assertAlmostEqual(hits[0].score, 1.0)
        self.assertAlmostEqual(hits[1].score, 0.8)


class RetrievalReplyTests(TestCase):
    def test_hit_adds_a_system_message_and_sources(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        chunk = Chunk.objects.create(
            source="handbook.md",
            position=2,
            text="The stack is Django.",
            embedding=[1.0, 0.0],
            embed_model="fake-embed",
        )
        fake = FakeModel()

        with (
            patch(
                "chat.views.retrieve",
                return_value=[Hit(chunk=chunk, score=0.71)],
            ),
            patch("chat.views.get_chat_model", return_value=fake),
        ):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "What is the stack?"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sources"],
            [{"source": "handbook.md", "position": 2, "score": 0.71}],
        )
        self.assertEqual(fake.calls[0][0]["role"], "system")
        self.assertIn("do not contain the answer", fake.calls[0][0]["text"])
        self.assertIn("handbook.md", fake.calls[0][0]["text"])
        self.assertIn("The stack is Django.", fake.calls[0][0]["text"])
        self.assertEqual(fake.calls[0][1]["role"], "assistant")
        self.assertEqual(
            fake.calls[0][-1],
            {"role": "user", "text": "What is the stack?"},
        )

    def test_no_hit_leaves_history_without_a_system_message(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        fake = FakeModel()

        with (
            patch("chat.views.retrieve", return_value=[]),
            patch("chat.views.get_chat_model", return_value=fake),
        ):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "Hello"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(fake.calls[0][0]["role"], "assistant")
        self.assertEqual(fake.calls[0][0]["text"], GREETING)
        self.assertEqual(fake.calls[0][-1], {"role": "user", "text": "Hello"})

    def test_embedder_failure_keeps_the_user_message(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]

        with patch(
            "chat.views.retrieve",
            side_effect=EmbedderUnavailable("down"),
        ):
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
