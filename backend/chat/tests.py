import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.embed.base import EmbedderUnavailable
from chat.llm.base import ModelReply, ModelUnavailable
from chat.models import Chunk, Conversation, Message
from chat.rag.chunking import split_paragraphs
from chat.rag.search import Hit, Retrieval, retrieve
from chat.route import SCHEMA, recent_block


class FakeModel:
    def __init__(self):
        self.calls = []

    def reply(self, messages, format=None, options=None):
        self.calls.append(messages)
        sent = {
            "model": "fake-model",
            "stream": False,
            "messages": [
                {"role": message["role"], "content": message["text"]}
                for message in messages
            ],
        }
        return ModelReply(
            text="The water is calm.",
            model="fake-model",
            sent=sent,
            message={"role": "assistant", "content": "The water is calm."},
        )


class FailingModel:
    def reply(self, messages, format=None, options=None):
        raise ModelUnavailable("down")


class FakeEmbedder:
    model_name = "fake-embed"

    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0]


class QuestionRouteModel:
    def reply(self, messages, format=None, options=None):
        sent = {
            "model": "fake-model",
            "stream": False,
            "messages": [
                {"role": message["role"], "content": message["text"]}
                for message in messages
            ],
        }
        return ModelReply(
            text="question",
            model="fake-model",
            sent=sent,
            message={"role": "assistant", "content": "question"},
        )


class ConversationApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_dir.cleanup)
        override = override_settings(LOG_DIR=self.log_dir.name)
        override.enable()
        self.addCleanup(override.disable)
        routed = patch("chat.route.get_chat_model", return_value=QuestionRouteModel())
        routed.start()
        self.addCleanup(routed.stop)
        patched = patch(
            "chat.views.retrieve",
            return_value=Retrieval(hits=[], scored=[]),
        )
        patched.start()
        self.addCleanup(patched.stop)

    def test_new_conversation_starts_empty(self):
        response = self.client.post(reverse("conversations"))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["messages"], [])

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
            retrieval = retrieve("when do the doors shut?")

        hits = retrieval.hits
        self.assertEqual([hit.chunk.text for hit in hits], ["close", "near"])
        self.assertAlmostEqual(hits[0].score, 1.0)
        self.assertAlmostEqual(hits[1].score, 0.8)
        kept = {
            item["position"]: item["kept"]
            for item in retrieval.scored
            if item["source"] == "handbook.md"
        }
        self.assertEqual(kept, {0: True, 1: True, 2: False, 3: False})
        self.assertNotIn(
            "other.md",
            {item["source"] for item in retrieval.scored},
        )


class RetrievalReplyTests(TestCase):
    def setUp(self):
        super().setUp()
        self.log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_dir.cleanup)
        override = override_settings(LOG_DIR=self.log_dir.name)
        override.enable()
        self.addCleanup(override.disable)
        routed = patch("chat.route.get_chat_model", return_value=QuestionRouteModel())
        routed.start()
        self.addCleanup(routed.stop)

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
                return_value=Retrieval(
                    hits=[Hit(chunk=chunk, score=0.71)],
                    scored=[
                        {
                            "source": "handbook.md",
                            "position": 2,
                            "score": 0.71,
                            "kept": True,
                        }
                    ],
                ),
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
        self.assertIn("You are Explorai.", fake.calls[0][0]["text"])
        self.assertIn(
            "Do not mention that you are answering from the passages.",
            fake.calls[0][0]["text"],
        )
        self.assertNotIn(
            "If they do not contain the answer, say so.",
            fake.calls[0][0]["text"],
        )
        self.assertIn("handbook.md", fake.calls[0][0]["text"])
        self.assertIn("The stack is Django.", fake.calls[0][0]["text"])
        self.assertEqual(
            fake.calls[0][1:],
            [{"role": "user", "text": "What is the stack?"}],
        )

    def test_no_hit_tells_the_model_the_notes_do_not_contain_the_answer(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        fake = FakeModel()

        with (
            patch("chat.views.retrieve", return_value=Retrieval(hits=[], scored=[])),
            patch("chat.views.get_chat_model", return_value=fake),
        ):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "Hello"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(fake.calls[0][0]["role"], "system")
        self.assertIn(
            "The notes do not contain the answer.",
            fake.calls[0][0]["text"],
        )
        self.assertEqual(
            fake.calls[0][1:],
            [{"role": "user", "text": "Hello"}],
        )

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


class ScriptedModel:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []
        self.formats = []
        self.options = []

    def reply(self, messages, format=None, options=None):
        self.calls.append(messages)
        self.formats.append(format)
        self.options.append(options)
        text = self.texts.pop(0)
        sent = {
            "model": "fake-model",
            "stream": False,
            "messages": [
                {"role": message["role"], "content": message["text"]}
                for message in messages
            ],
        }
        return ModelReply(
            text=text,
            model="fake-model",
            sent=sent,
            message={"role": "assistant", "content": text},
        )


class TurnLogTests(TestCase):
    def setUp(self):
        super().setUp()
        self.log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_dir.cleanup)
        override = override_settings(LOG_DIR=self.log_dir.name)
        override.enable()
        self.addCleanup(override.disable)
        routed = patch("chat.route.get_chat_model", return_value=QuestionRouteModel())
        routed.start()
        self.addCleanup(routed.stop)

    def test_turn_log_contains_the_sent_request_and_received_message(self):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        fake = FakeModel()
        with (
            patch(
                "chat.views.retrieve",
                return_value=Retrieval(hits=[], scored=[]),
            ),
            patch("chat.views.get_chat_model", return_value=fake),
        ):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "Hello"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        files = sorted(Path(self.log_dir.name).glob("*.json"))
        self.assertEqual(len(files), 1)
        record = json.loads(files[0].read_text())
        self.assertEqual(record["question"], "Hello")
        self.assertEqual(record["sent"]["messages"][-1]["content"], "Hello")
        self.assertEqual(
            record["received"],
            {"role": "assistant", "content": "The water is calm."},
        )
        self.assertIsNone(record["error"])
        self.assertIn("The notes do not contain the answer.", record["system"])

    def test_only_ten_logs_are_kept(self):
        from chat.log import write_turn

        for number in range(11):
            write_turn({"n": number})

        files = sorted(Path(self.log_dir.name).glob("*.json"))
        self.assertEqual(len(files), 10)
        kept = [json.loads(path.read_text())["n"] for path in files]
        self.assertEqual(kept, list(range(1, 11)))


class CasualRouteTests(TestCase):
    def setUp(self):
        super().setUp()
        self.log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_dir.cleanup)
        override = override_settings(LOG_DIR=self.log_dir.name)
        override.enable()
        self.addCleanup(override.disable)

    def post_turn(self, model, text):
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        with (
            patch("chat.route.get_chat_model", return_value=model),
            patch("chat.views.get_chat_model", return_value=model),
            patch("chat.views.retrieve", return_value=Retrieval(hits=[], scored=[])) as retrieve,
        ):
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": text},
                content_type="application/json",
            )
        return response, retrieve, model

    def test_chat_skips_retrieval_and_uses_the_short_prompt(self):
        model = ScriptedModel(['{"route": "chat"}', "Hello."])
        response, retrieve, model = self.post_turn(model, "Jónapot!")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], [])
        retrieve.assert_not_called()
        self.assertEqual(model.formats[0], SCHEMA)
        self.assertEqual(model.options[0], {"temperature": 0})
        self.assertEqual(
            model.calls[1][0]["text"],
            "You are Explorai. Respond briefly and naturally. "
            "Do not state facts about the notes.",
        )
        files = sorted(Path(self.log_dir.name).glob("*.json"))
        record = json.loads(files[0].read_text())
        self.assertEqual(record["route"]["decision"], "chat")
        self.assertIsNone(record["retrieval"])
        self.assertIsNone(record["query"])
        self.assertEqual(record["route"]["received"]["content"], '{"route": "chat"}')

    def test_question_still_retrieves(self):
        model = ScriptedModel(['{"route": "question"}', "The water is calm."])
        response, retrieve, model = self.post_turn(model, "What is the interface?")

        self.assertEqual(response.status_code, 200)
        retrieve.assert_called_once_with("User: What is the interface?")
        self.assertIn(
            "Answer only from the passages.",
            model.calls[1][0]["text"],
        )
        record = json.loads(
            sorted(Path(self.log_dir.name).glob("*.json"))[-1].read_text()
        )
        self.assertEqual(record["route"]["decision"], "question")
        self.assertEqual(record["query"], "User: What is the interface?")
        self.assertIsNotNone(record["retrieval"])

    def test_invalid_json_still_retrieves(self):
        model = ScriptedModel(["maybe both", "The water is calm."])
        response, retrieve, model = self.post_turn(model, "Hello")

        self.assertEqual(response.status_code, 200)
        retrieve.assert_called_once_with("User: Hello")
        self.assertIn(
            "The notes do not contain the answer.",
            model.calls[1][0]["text"],
        )

    def test_follow_up_retrieves_the_recent_block(self):
        model = ScriptedModel(
            [
                '{"route": "question"}',
                "The interface is a TypeScript page.",
                '{"route": "question"}',
                "Django stores the conversations.",
            ]
        )
        created = self.client.post(reverse("conversations"))
        conversation_id = created.json()["id"]
        with (
            patch("chat.route.get_chat_model", return_value=model),
            patch("chat.views.get_chat_model", return_value=model),
            patch("chat.views.retrieve", return_value=Retrieval(hits=[], scored=[])) as retrieve,
        ):
            self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "What is the interface?"},
                content_type="application/json",
            )
            response = self.client.post(
                reverse("conversation-message", args=[conversation_id]),
                data={"text": "tell me more"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            retrieve.call_args.args[0],
            "User: What is the interface?\n"
            "Assistant: The interface is a TypeScript page.\n"
            "User: tell me more",
        )

    def test_recent_block_keeps_two_past_messages(self):
        class Line:
            def __init__(self, role, text):
                self.role = role
                self.text = text

        messages = [
            Line("user", "one"),
            Line("assistant", "two"),
            Line("user", "three"),
            Line("assistant", "four"),
            Line("user", "five"),
        ]
        self.assertEqual(
            recent_block(messages),
            "User: three\nAssistant: four\nUser: five",
        )

    def test_classifier_failure_still_retrieves(self):
        class DownThenAnswer:
            def __init__(self):
                self.calls = []

            def reply(self, messages, format=None, options=None):
                self.calls.append(messages)
                if len(self.calls) == 1:
                    raise ModelUnavailable("down")
                return ModelReply(
                    text="The water is calm.",
                    model="fake-model",
                    sent={"messages": []},
                    message={"role": "assistant", "content": "The water is calm."},
                )

        model = DownThenAnswer()
        response, retrieve, model = self.post_turn(model, "Hello")

        self.assertEqual(response.status_code, 200)
        retrieve.assert_called_once_with("User: Hello")
        self.assertIn("Answer only from the passages.", model.calls[1][0]["text"])
