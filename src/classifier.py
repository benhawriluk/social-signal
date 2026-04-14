"""LLM-based document classification via OpenRouter."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import OpenAI

from src.config import settings
from src.models import ClassificationResult, RawDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

_PROMPT_FILE = Path(__file__).parent.parent / "docs" / "classifier_prompt.md"
_SPLIT_MARKER = "\n---\n\nPOST TO CLASSIFY:"


def _load_prompt() -> tuple[str, str]:
    """Load and split docs/classifier_prompt.md into (system_prompt, user_template).

    The file is split at the '--- POST TO CLASSIFY:' marker.
    The user template retains the 'POST TO CLASSIFY:' header and uses
    {{subreddit}}, {{post_id}}, {{title}}, {{body}} as placeholders.
    """
    raw = _PROMPT_FILE.read_text(encoding="utf-8")
    if _SPLIT_MARKER not in raw:
        raise ValueError(f"Could not find split marker in {_PROMPT_FILE}")
    system, user_section = raw.split(_SPLIT_MARKER, maxsplit=1)
    user_template = "POST TO CLASSIFY:" + user_section
    return system.strip(), user_template.strip()


SYSTEM_PROMPT, USER_TEMPLATE = _load_prompt()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_document(doc: RawDocument) -> ClassificationResult | None:
    """Classify a single document via OpenRouter.

    Fails fast on any error — no retries. Unclassified posts are caught
    on re-run since the DB is the checkpoint.
    """
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    user_message = (
        USER_TEMPLATE.replace("{{subreddit}}", doc.subreddit)
        .replace("{{post_id}}", doc.source_id)
        .replace("{{title}}", doc.title or "")
        .replace("{{body}}", doc.body)
    )

    try:
        response = client.chat.completions.create(
            model=settings.classifier_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content
        data = json.loads(raw_text)
        return ClassificationResult.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Parse error for %s: %s", doc.source_id, e)
        return None
    except Exception as e:
        logger.warning("API error for %s: %s", doc.source_id, e)
        return None
