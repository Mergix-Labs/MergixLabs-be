from django.conf import settings
from rest_framework import serializers

from .models import RAGConversation, RAGMessage, SharedConversation


class RAGMessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = RAGMessage
        fields = [
            "id",
            "role",
            "content",
            "created_at",
            "reaction",
            "is_pinned",
        ]


class RAGConversationListSerializer(serializers.ModelSerializer):

    class Meta:
        model = RAGConversation
        fields = ["id", "title", "is_pinned", "created_at", "updated_at"]


class RAGConversationDetailSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = RAGConversation
        fields = [
            "id",
            "title",
            "is_pinned",
            "messages",
            "created_at",
            "updated_at",
        ]

    def get_messages(self, obj):
        ordered_messages = obj.messages.all().order_by("created_at", "id")
        return RAGMessageSerializer(
            ordered_messages, many=True, context=self.context
        ).data


class MessageReactionSerializer(serializers.Serializer):
    reaction = serializers.ChoiceField(choices=["like", "dislike"])


class ShareConversationSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = SharedConversation
        fields = ["token", "share_url", "created_at"]

    def get_share_url(self, obj):
        base_url = settings.FRONTEND_URL.rstrip("/")
        return f"{base_url}/shared-chat/{obj.token}"
