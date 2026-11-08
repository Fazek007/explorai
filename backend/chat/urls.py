from django.urls import path

from chat.views import conversation_detail, conversation_message, conversations

urlpatterns = [
    path("conversations/", conversations, name="conversations"),
    path(
        "conversations/<uuid:conversation_id>/",
        conversation_detail,
        name="conversation-detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/",
        conversation_message,
        name="conversation-message",
    ),
]
