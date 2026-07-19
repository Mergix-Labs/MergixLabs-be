import logging
import re

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RAGConversation, RAGMessage, SharedConversation
from .serializers import (
    MessageReactionSerializer,
    RAGConversationDetailSerializer,
    RAGConversationListSerializer,
    ShareConversationSerializer,
)

logger = logging.getLogger("fintech_ai")


def _derive_conversation_title(message: str) -> str:
    cleaned = re.sub(r"\s+", " ", (message or "").strip())
    if not cleaned:
        return "New Chat"
    if len(cleaned) <= 48:
        return cleaned
    trimmed = cleaned[:45].rsplit(" ", 1)[0].strip() or cleaned[:45].strip()
    return f"{trimmed}..."


def _get_owned_conversation(user, conversation_id):
    """Fetch a conversation, guaranteeing it belongs to `user` (prevents IDOR)."""
    return get_object_or_404(RAGConversation, id=conversation_id, user=user)


def _get_owned_message(user, message_id, **filters):
    """Fetch a message, guaranteeing its conversation belongs to `user` (prevents IDOR)."""
    return get_object_or_404(
        RAGMessage.objects.select_related("conversation"),
        id=message_id,
        conversation__user=user,
        **filters,
    )


class RAGConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = RAGConversation.objects.filter(user=request.user)
        serializer = RAGConversationListSerializer(
            conversations, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        title = (request.data.get("title") or "New Chat").strip() or "New Chat"
        conversation = RAGConversation.objects.create(user=request.user, title=title)
        serializer = RAGConversationDetailSerializer(
            conversation, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RAGConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        conversation = _get_owned_conversation(request.user, id)
        serializer = RAGConversationDetailSerializer(
            conversation, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        conversation = _get_owned_conversation(request.user, id)
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        serializer = MessageReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = _get_owned_message(
            request.user, message_id, role=RAGMessage.ROLE_AI
        )

        message.reaction = serializer.validated_data["reaction"]
        message.reaction_by_user = request.user
        message.reaction_at = timezone.now()
        message.save(update_fields=["reaction", "reaction_by_user", "reaction_at"])

        return Response({"success": True, "reaction": message.reaction})


class RemoveReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, message_id):
        message = _get_owned_message(request.user, message_id)

        message.reaction = None
        message.reaction_by_user = None
        message.reaction_at = None
        message.save(update_fields=["reaction", "reaction_by_user", "reaction_at"])

        return Response({"success": True, "reaction": None})


class PinMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        message = _get_owned_message(request.user, message_id)
        message.is_pinned = True
        message.save(update_fields=["is_pinned"])
        return Response(
            {"success": True, "pinned": True, "message_id": message.id},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, message_id):
        message = _get_owned_message(request.user, message_id)
        message.is_pinned = False
        message.save(update_fields=["is_pinned"])
        return Response(
            {"success": True, "pinned": False, "message_id": message.id},
            status=status.HTTP_200_OK,
        )


class PinConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = _get_owned_conversation(request.user, conversation_id)
        conversation.is_pinned = True
        conversation.save(update_fields=["is_pinned"])
        return Response(
            {
                "success": True,
                "pinned": True,
                "conversation_id": str(conversation.id),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, conversation_id):
        conversation = _get_owned_conversation(request.user, conversation_id)
        conversation.is_pinned = False
        conversation.save(update_fields=["is_pinned"])
        return Response(
            {
                "success": True,
                "pinned": False,
                "conversation_id": str(conversation.id),
            },
            status=status.HTTP_200_OK,
        )


class ShareConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = _get_owned_conversation(request.user, conversation_id)

        shared_link, _created = SharedConversation.objects.get_or_create(
            conversation=conversation,
            defaults={"created_by": request.user},
        )

        serializer = ShareConversationSerializer(shared_link)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SharedConversationDetailView(APIView):
    """Public read-only view of a shared conversation via its token.

    Intentionally unauthenticated: link-sharing is only useful if a
    recipient without an account can open the link. No user-owned data
    beyond the conversation content already published by its owner is
    exposed here, and no mutation is possible through this endpoint.
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        shared = get_object_or_404(
            SharedConversation.objects.select_related("conversation"),
            token=token,
            is_active=True,
        )
        conversation = shared.conversation
        messages = conversation.messages.all().order_by("created_at", "id")

        data = {
            "title": conversation.title,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }
        return Response(data)


class ContinueSharedConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        shared = get_object_or_404(
            SharedConversation, token=token, is_active=True
        )
        source_conversation = shared.conversation

        new_conversation = RAGConversation.objects.create(
            user=request.user, title=source_conversation.title
        )

        source_messages = source_conversation.messages.all().order_by(
            "created_at", "id"
        )
        RAGMessage.objects.bulk_create(
            [
                RAGMessage(
                    conversation=new_conversation,
                    role=msg.role,
                    content=msg.content,
                )
                for msg in source_messages
            ]
        )

        return Response(
            {
                "success": True,
                "conversation_id": str(new_conversation.id),
            },
            status=status.HTTP_201_CREATED,
        )
