
import logging
import re
import google.generativeai as genai

from .ingestion import _setup_apis

logger = logging.getLogger("fintech_ai")

_setup_apis()

# -----------------------------
# FINTECH KEYWORDS
# -----------------------------
FINTECH_KEYWORDS = {
    "sip",
    "mutual fund",
    "mutual funds",
    "insurance",
    "loan",
    "personal loan",
    "home loan",
    "education loan",
    "credit card",
    "debit card",
    "fd",
    "fixed deposit",
    "rd",
    "recurring deposit",
    "tax",
    "income tax",
    "80c",
    "investment",
    "investing",
    "portfolio",
    "wealth",
    "wealth management",
    "financial planning",
    "retirement",
    "retirement planning",
    "stocks",
    "stock market",
    "share market",
    "equity",
    "trading",
    "bond",
    "bonds",
    "etf",
    "index fund",
    "nps",
    "epf",
    "ppf",
    "emi",
    "interest rate",
    "upi",
    "digital payment",
    "cibil",
    "credit score",
    "crypto",
    "bitcoin",
    "ethereum",

    # App Features
    "goal",
    "goals",
    "goal creation",
    "family tree",
    "family member",
    "dashboard",
    "profile",
    "login",
    "otp",
    "kyc",
    "portfolio tracker",
    "investment tracking",
    "calculator",
    "wealth projection",
}

# -----------------------------
# GREETING WORDS
# -----------------------------
GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "thanks",
    "thank you",
    "what is samaira ai",
    "who are you",
    "what can you do",
}

# -----------------------------
# FOLLOWUP PATTERNS
# -----------------------------
FOLLOWUP_PATTERNS = [
    "is it good",
    "what do you think",
    "which one",
    "that one",
    "this one",
    "can i do that",
    "should i do that",
    "is that better",
    "tell me more",
    "explain more",
    "why",
    "how",
    "then what",
    "next",
]

# -----------------------------
# GEMINI FALLBACK PROMPT
# -----------------------------
CLASSIFIER_PROMPT = """
You are a domain classifier.

Return ONLY:

FINTECH
NON_FINTECH

Finance includes:
- Banking
- Loans
- Investments
- SIP
- Mutual Funds
- Insurance
- Tax
- Retirement
- Wealth Management
- Stocks
- Trading
- Credit Cards
- UPI
- Financial Planning
- Fintech Applications

Question:
{question}
"""


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def is_greeting(question: str) -> bool:
    q = normalize(question)

    return q in GREETING_WORDS


def is_followup_question(
    question: str,
    has_history: bool = False
) -> bool:

    if not has_history:
        return False

    q = normalize(question)

    for pattern in FOLLOWUP_PATTERNS:
        if pattern in q:
            return True

    if len(q.split()) <= 3:
        return True

    return False


def contains_fintech_keyword(question: str) -> bool:

    q = normalize(question)

    for keyword in FINTECH_KEYWORDS:
        if keyword in q:
            return True

    return False


def gemini_fintech_classifier(question: str) -> bool:
    """
    Only used as LAST fallback.
    """

    try:

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config={
                "temperature": 0,
                "max_output_tokens": 20,
            },
        )

        response = model.generate_content(
            CLASSIFIER_PROMPT.format(
                question=question
            )
        )

        answer = (
            getattr(response, "text", "")
            .strip()
            .upper()
        )

        logger.info(
            "Gemini Classifier Result: %s",
            answer
        )

        return answer.startswith(
            "FINTECH"
        )

    except Exception as exc:

        logger.exception(
            "Gemini classifier failed: %s",
            exc
        )

        # Safe fallback
        return True


def is_fintech_question(
    question: str,
    has_history: bool = False
) -> bool:
    """
    Production entrypoint.

    Order:
    1. Greeting
    2. Follow-up
    3. Keyword Match
    4. Gemini Fallback
    """

    if not question:
        return False

    if is_greeting(question):
        return True

    if is_followup_question(
        question,
        has_history
    ):
        return True

    if contains_fintech_keyword(
        question
    ):
        return True

    return gemini_fintech_classifier(
        question
    )