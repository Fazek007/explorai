import uuid

from django.db import models

GREETING = "Hello! Nice day for fishing, aint it?"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Chunk(models.Model):
    source = models.CharField(max_length=255)
    position = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField()
    embed_model = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source", "position"]


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=16)
    text = models.TextField()
    model = models.CharField(max_length=128, blank=True)
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
