import uuid
import secrets

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class KnowledgeDocument(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to="samaira_ai/documents/",
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "txt"])],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    error_log = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_id = models.CharField(
        max_length=100, unique=True, help_text="Pinecone vector ID"
    )
    text = models.TextField(help_text="The extracted child text segment")
    parent_text = models.TextField(
        help_text="The larger surrounding parent context block"
    )
    page_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_id} (Page {self.page_number or 'N/A'})"


class RAGConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rag_conversations",
    )
    title = models.CharField(max_length=150, default="New RAG Chat")
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.user} - {self.title}"


class RAGMessage(models.Model):
    ROLE_USER = "user"
    ROLE_AI = "ai"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_AI, "AI"),
    ]
    REACTION_CHOICES = [
        ("like", "Like"),
        ("dislike", "Dislike"),
    ]

    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(
        RAGConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    reaction = models.CharField(
        max_length=10, choices=REACTION_CHOICES, null=True, blank=True
    )
    reaction_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reacted_rag_messages",
    )
    reaction_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["reaction"]),
            models.Index(fields=["reaction_at"]),
        ]

    def __str__(self):
        return f"Msg {self.id} in RAG Conversation {self.conversation_id} ({self.role})"


class SharedConversation(models.Model):
    conversation = models.ForeignKey(
        RAGConversation,
        on_delete=models.CASCADE,
        related_name="shared_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_conversations",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.token


@receiver(post_save, sender=KnowledgeDocument)
def trigger_ingestion_on_save(sender, instance, created, **kwargs):
    update_fields = kwargs.get("update_fields")
    if update_fields and ("is_processed" in update_fields or "error_log" in update_fields):
        return
    from .tasks import ingest_document_task
    ingest_document_task.delay(instance.id)


@receiver(post_delete, sender=KnowledgeDocument)
def trigger_deletion_on_delete(sender, instance, **kwargs):
    from .tasks import delete_document_task
    delete_document_task.delay(instance.id)
