
import re
from typing import Optional, Tuple

from .domain_classifier import is_fintech_question


BLOCK_RESPONSE = (
    "I can only assist with financial, banking, investment, "
    "insurance, tax, and fintech-related questions."
)

# =====================================================
# GREETING RESPONSES
# =====================================================

GREETING_RESPONSES = {
    "how are you":
        "I'm doing well. How can I assist you today?",

    "who are you":
        (
            "I am Fintech AI, your financial assistant. "
            "I can help with investments, SIPs, mutual funds, "
            "insurance, tax planning, financial goals, and platform navigation."
        ),

    "what is your name":
        "I am Fintech AI, your financial assistant.",

    "what is fintech ai":
        (
            "Fintech AI is an AI-powered financial assistant that helps users "
            "with investments, SIPs, mutual funds, insurance, financial planning, "
            "goal tracking, and navigation within the platform."
        ),

    "thanks":
        "You're welcome!",

    "thank you":
        "You're welcome!",

    "help":
        (
            "I can help with investments, SIPs, mutual funds, "
            "insurance, taxes, financial planning, and platform navigation."
        ),
}


# =====================================================
# APP QUESTIONS
# =====================================================

APP_INFO_RESPONSES = {
    "what can you do":
        (
            "I can help with financial planning, investments, SIPs, "
            "mutual funds, insurance, taxes, goals, and platform navigation."
        ),

    "how can you help me":
        (
            "I can answer financial questions, explain investment products, "
            "assist with goals, and guide you through the platform."
        ),

    "tell me about samaira":
        (
            "Fintech AI is a financial assistant designed to help users "
            "manage and understand their finances."
        ),
}


# =====================================================
# GREETING PATTERNS
# =====================================================

GREETING_PATTERNS = [
    r"^hi+$",
    r"^hii+$",
    r"^hello+$",
    r"^helo+$",
    r"^hey+$",
    r"^heyy+$",
    r"^yo+$",
    r"^sup+$",
    r"^good morning$",
    r"^good afternoon$",
    r"^good evening$",
    r"^good night$",
    r"^namaste$",
    r"^hello fintech$",
    r"^hi fintech$",
    r"^hey fintech$",
    r"^start$",
]


# =====================================================
# FOLLOWUP WORDS
# =====================================================

FOLLOWUP_WORDS = {
    "it",
    "this",
    "that",
    "these",
    "those",
    "they",
    "them",
    "one",
}

FOLLOWUP_PHRASES = [
    "is it good",
    "what do you think",
    "tell me more",
    "explain more",
    "which one",
    "what about that",
    "what about this",
    "can i use it",
    "is that better",
]


# =====================================================
# HELPERS
# =====================================================

def normalize_text(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (text or "").lower().strip()
    )


def is_greeting(text: str) -> bool:

    text = normalize_text(text)

    if text in GREETING_RESPONSES:
        return True

    for pattern in GREETING_PATTERNS:
        if re.match(pattern, text):
            return True

    return False


def get_greeting_response(text: str) -> str:

    text = normalize_text(text)

    if text in GREETING_RESPONSES:
        return GREETING_RESPONSES[text]

    return "Hello! How can I help you with your financial needs today?"


def is_app_question(text: str) -> bool:
    return normalize_text(text) in APP_INFO_RESPONSES


def get_app_response(text: str) -> Optional[str]:
    return APP_INFO_RESPONSES.get(
        normalize_text(text)
    )


def is_followup_question(
    text: str,
    has_history: bool = False
) -> bool:

    if not has_history:
        return False

    text = normalize_text(text)

    # Explicit phrases
    for phrase in FOLLOWUP_PHRASES:
        if phrase in text:
            return True

    # Very short messages
    if len(text.split()) <= 5:
        return True

    # Pronoun-based followup
    words = set(text.split())

    if words.intersection(FOLLOWUP_WORDS):
        return True

    return False


# =====================================================
# MAIN VALIDATOR
# =====================================================

def validate_query(
    text: str,
    has_history: bool = False
) -> Tuple[bool, Optional[str]]:

    text = (text or "").strip()

    if not text:
        return False, "Question is required."

    # Greetings
    if is_greeting(text):
        return True, get_greeting_response(text)

    # Samaira / App Questions
    if is_app_question(text):
        return True, get_app_response(text)

    # Follow-up Questions
    if is_followup_question(
        text=text,
        has_history=has_history
    ):
        return True, None

    # Fintech Validation
    if is_fintech_question(
        question=text,
        has_history=has_history
    ):
        return True, None

    # Out of Scope
    return False, BLOCK_RESPONSE