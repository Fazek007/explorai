import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from chat.embed.base import EmbedderUnavailable
from chat.llm import get_chat_model
from chat.llm.base import ModelUnavailable
from chat.log import write_turn
from chat.models import GREETING, Conversation, Message
from chat.rag.search import retrieve
from chat.route import route


def message_payload(message):
    return {
        "id": str(message.id),
        "role": message.role,
        "text": message.text,
        "model": message.model,
        "sources": message.sources,
    }


def conversation_payload(conversation):
    return {
        "id": str(conversation.id),
        "messages": [
            message_payload(message)
            for message in conversation.messages.all()
        ],
    }


def read_json(request):
    if not request.body:
        return {}
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    return body


INSTRUCTION = (
    "You are Explorai. Answer only from the passages. "
    "Do not mention that you are answering from the passages."
)

CASUAL = (
    "You are Explorai. Respond briefly and naturally. "
    "Do not state facts about the notes."
)


def context_message(hits):
    if not hits:
        return f"{INSTRUCTION}\n\nThe notes do not contain the answer."
    passages = "\n\n".join(
        f"{hit.chunk.source}\n{hit.chunk.text}" for hit in hits
    )
    return f"{INSTRUCTION}\n\n{passages}"


def turn_record(question, retrieval, system, route_decision, reply=None, error=None):
    if retrieval is None:
        retrieval_payload = None
    else:
        retrieval_payload = {
            "embed_model": settings.OLLAMA_EMBED_MODEL,
            "top_k": settings.RAG_TOP_K,
            "min_score": settings.RAG_MIN_SCORE,
            "scored": retrieval.scored,
        }
    return {
        "kind": "chat",
        "question": question,
        "route": {
            "sent": route_decision.sent,
            "received": route_decision.received,
            "decision": route_decision.decision,
        },
        "retrieval": retrieval_payload,
        "system": system,
        "sent": None if reply is None else reply.sent,
        "received": None if reply is None else reply.message,
        "error": error,
    }


def create_conversation():
    conversation = Conversation.objects.create()
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        text=GREETING,
    )
    return conversation


@csrf_exempt
def conversations(request):
    if request.method == "POST":
        conversation = create_conversation()
        return JsonResponse(conversation_payload(conversation), status=201)
    if request.method == "DELETE":
        Conversation.objects.all().delete()
        return HttpResponse(status=204)
    return JsonResponse({"error": "Method not allowed."}, status=405)


@csrf_exempt
def conversation_detail(request, conversation_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found."}, status=404)
    return JsonResponse(conversation_payload(conversation))


@csrf_exempt
def conversation_message(request, conversation_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found."}, status=404)

    body = read_json(request)
    if body is None or "text" not in body or not isinstance(body["text"], str):
        return JsonResponse({"error": "A text field is required."}, status=400)
    text = body["text"].strip()
    if not text:
        return JsonResponse({"error": "A text field is required."}, status=400)

    Message.objects.create(conversation=conversation, role="user", text=text)
    decision = route(text)
    retrieval = None
    if decision.decision == "chat":
        hits = []
        system = CASUAL
    else:
        try:
            retrieval = retrieve(text)
        except EmbedderUnavailable as exc:
            write_turn(turn_record(text, None, None, decision, error=str(exc)))
            return JsonResponse({"error": "The model is unavailable."}, status=502)
        hits = retrieval.hits
        system = context_message(hits)
    history = [{"role": "system", "text": system}]
    history.extend(
        {"role": message.role, "text": message.text}
        for message in conversation.messages.all()
    )
    try:
        reply = get_chat_model().reply(history)
    except ModelUnavailable as exc:
        record = turn_record(text, retrieval, system, decision, error=str(exc))
        record["sent"] = exc.sent
        write_turn(record)
        return JsonResponse({"error": "The model is unavailable."}, status=502)

    write_turn(turn_record(text, retrieval, system, decision, reply=reply))

    if decision.decision == "chat":
        sources = []
    else:
        sources = [
            {
                "source": hit.chunk.source,
                "position": hit.chunk.position,
                "score": hit.score,
            }
            for hit in hits
        ]
    message = Message.objects.create(
        conversation=conversation,
        role="assistant",
        text=reply.text,
        model=reply.model,
        sources=sources,
    )
    return JsonResponse(
        {
            "text": message.text,
            "model": message.model,
            "sources": message.sources,
        }
    )
