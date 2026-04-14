"""Text cleaning and PII scrubbing."""

from __future__ import annotations

import re

import bleach
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from src.config import settings
from src.models import RawDocument

# PII patterns
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
URL_RE = re.compile(r"https?://\S+")

# Reddit markdown artifacts
REDDIT_QUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)
REDDIT_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
BOLD_ITALIC_RE = re.compile(r"[*_]{1,3}")
STRIKETHROUGH_RE = re.compile(r"~~")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")  # keep link text, drop URL


def clean_text(text: str) -> str:
    """Strip HTML, markdown artifacts, and normalize whitespace."""
    # Strip HTML tags
    text = bleach.clean(text, tags=[], strip=True)

    # Reddit markdown
    text = REDDIT_QUOTE_RE.sub("", text)
    text = REDDIT_HEADER_RE.sub("", text)
    text = BOLD_ITALIC_RE.sub("", text)
    text = STRIKETHROUGH_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)  # [text](url) -> text

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def scrub_pii(text: str) -> str:
    """Remove emails, phone numbers, and URLs."""
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    text = URL_RE.sub("[link]", text)
    return text


def detect_language(text: str) -> str | None:
    """Return ISO 639-1 language code, or None if detection fails."""
    try:
        return detect(text)
    except LangDetectException:
        return None


def clean_document(doc: RawDocument) -> RawDocument | None:
    """Full cleaning pipeline for a single document.

    Returns None if the document should be filtered out.
    """
    cleaned = clean_text(doc.body)
    cleaned = scrub_pii(cleaned)

    # Length filter
    if len(cleaned) < settings.min_text_length:
        return None

    # Language filter (English only)
    lang = detect_language(cleaned)
    if lang and lang != "en":
        return None

    return doc.model_copy(update={"body": cleaned})


def clean_batch(docs: list[RawDocument]) -> list[RawDocument]:
    """Clean a batch of documents, filtering out invalid ones."""
    results = []
    for doc in docs:
        cleaned = clean_document(doc)
        if cleaned is not None:
            results.append(cleaned)
    return results
