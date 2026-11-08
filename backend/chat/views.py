import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from chat.llm import get_chat_model
from chat.llm.base import ModelUnavailable
from chat.models import GREETING, Conversation, Message


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
    history = [
        {"role": message.role, "text": message.text}
        for message in conversation.messages.all()
    ]
    try:
        reply = get_chat_model().reply(history)
    except ModelUnavailable:
        return JsonResponse({"error": "The model is unavailable."}, status=502)

    message = Message.objects.create(
        conversation=conversation,
        role="assistant",
        text=reply.text,
        model=reply.model,
        sources=[],
    )
    return JsonResponse(
        {
            "text": message.text,
            "model": message.model,
            "sources": message.sources,
        }
    )
