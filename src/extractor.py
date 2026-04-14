"""Pass 2 extraction via OpenRouter — extracts free-text summaries from flagged posts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import OpenAI

from src.config import settings
from src.models import ExtractionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

_PROMPT_FILE = Path(__file__).parent.parent / "docs" / "extraction_prompt.md"
_SPLIT_MARKER = "\n---\n\nEXTRACT:"


def _load_prompt() -> tuple[str, str]:
    raw = _PROMPT_FILE.read_text(encoding="utf-8")
    if _SPLIT_MARKER not in raw:
        raise ValueError(f"Could not find split marker in {_PROMPT_FILE}")
    system, user_section = raw.split(_SPLIT_MARKER, maxsplit=1)
    user_template = "EXTRACT:" + user_section
    return system.strip(), user_template.strip()


SYSTEM_PROMPT, USER_TEMPLATE = _load_prompt()

# Maps Pass 1 classification paths to extraction field names
TRIGGER_MAP = {
    "q06_vulnerable_populations": ("company_responsibility_mentioned", "company_responsibility"),
    "q07_model_change_harm": ("user_proposes_remedy", "proposed_remedy"),
    "q08_human_relationships": ("adjudication_norms_proposed", "adjudication_norms"),
    "q11_data_provenance_trust": ("solutions_proposed", "provenance_solutions"),
    "q17_disintermediation": ("mechanism_described", "disintermediation_mechanism"),
}


def get_extract_fields(classifications: dict) -> list[str]:
    """Determine which fields need extraction based on Pass 1 classifications."""
    fields = []
    for theme_key, (subflag, field_name) in TRIGGER_MAP.items():
        theme = classifications.get(theme_key, {})
        if theme.get("present") and theme.get(subflag):
            fields.append(field_name)
    return fields


def extract_document(
    post_id: str,
    subreddit: str,
    title: str,
    body: str,
    extract_fields: list[str],
) -> ExtractionResult | None:
    """Run Pass 2 extraction on a single document.

    Fails fast — unextracted posts are caught on re-run.
    """
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    user_message = (
        USER_TEMPLATE.replace("{{extract_fields}}", ", ".join(extract_fields))
        .replace("{{subreddit}}", subreddit)
        .replace("{{post_id}}", post_id)
        .replace("{{title}}", title or "")
        .replace("{{body}}", body or "")
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
        data["post_id"] = post_id
        return ExtractionResult.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Parse error for %s: %s", post_id, e)
        return None
    except Exception as e:
        logger.warning("API error for %s: %s", post_id, e)
        return None
