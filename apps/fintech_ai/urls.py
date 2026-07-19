from django.urls import path

from .views import (
    RAGConversationListView,
    RAGConversationDetailView,
    MessageReactionView,
    RemoveReactionView,
    PinMessageView,
    PinConversationView,
    ShareConversationView,
    SharedConversationDetailView,
    ContinueSharedConversationView,
)

app_name = "fintech_ai"

urlpatterns = [

    # ==========================================================
    # Conversation
    # ==========================================================

    path(
        "conversations/",
        RAGConversationListView.as_view(),
        name="conversation-list",
    ),

    path(
        "conversations/<uuid:id>/",
        RAGConversationDetailView.as_view(),
        name="conversation-detail",
    ),

    # ==========================================================
    # Pin Conversation
    # ==========================================================

    path(
        "conversations/<uuid:conversation_id>/pin/",
        PinConversationView.as_view(),
        name="pin-conversation",
    ),

    # ==========================================================
    # Message Reaction
    # ==========================================================

    path(
        "messages/<int:message_id>/reaction/",
        MessageReactionView.as_view(),
        name="message-reaction",
    ),

    path(
        "messages/<int:message_id>/reaction/remove/",
        RemoveReactionView.as_view(),
        name="remove-message-reaction",
    ),

    # ==========================================================
    # Pin Message
    # ==========================================================

    path(
        "messages/<int:message_id>/pin/",
        PinMessageView.as_view(),
        name="pin-message",
    ),

    # ==========================================================
    # Share Conversation
    # ==========================================================

    path(
        "conversations/<uuid:conversation_id>/share/",
        ShareConversationView.as_view(),
        name="share-conversation",
    ),

    path(
        "shared/<str:token>/",
        SharedConversationDetailView.as_view(),
        name="shared-conversation-detail",
    ),

    path(
        "shared/<str:token>/continue/",
        ContinueSharedConversationView.as_view(),
        name="continue-shared-conversation",
    ),
]