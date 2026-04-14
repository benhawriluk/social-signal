"""Deduplication via exact ID matching and SimHash fingerprinting."""

from __future__ import annotations

from simhash import Simhash

from src.models import RawDocument

SIMHASH_DISTANCE_THRESHOLD = 5  # bits — lower = stricter


def compute_simhash(text: str) -> int:
    """Compute a SimHash fingerprint for the given text.

    Returns a signed 64-bit integer (fits in PostgreSQL bigint).
    """
    value = Simhash(text).value
    # Convert unsigned 64-bit to signed for Postgres bigint range
    if value >= (1 << 63):
        value -= 1 << 64
    return value


def simhash_distance(hash1: int, hash2: int) -> int:
    """Hamming distance between two SimHash values."""
    return Simhash(hash1).distance(Simhash(hash2))


def deduplicate(docs: list[RawDocument], existing_ids: set[str] | None = None) -> list[RawDocument]:
    """Remove duplicates from a batch of documents.

    - Exact match: skip documents whose source_id is in existing_ids.
    - Near-duplicate: skip documents whose SimHash is within threshold of an already-seen doc.
    """
    existing_ids = existing_ids or set()
    seen_ids: set[str] = set(existing_ids)
    seen_hashes: list[int] = []
    unique: list[RawDocument] = []

    for doc in docs:
        # Exact ID match
        if doc.source_id in seen_ids:
            continue

        # SimHash near-duplicate check
        doc_hash = compute_simhash(doc.body)
        is_dup = False
        for existing_hash in seen_hashes:
            if simhash_distance(doc_hash, existing_hash) <= SIMHASH_DISTANCE_THRESHOLD:
                is_dup = True
                break

        if is_dup:
            continue

        seen_ids.add(doc.source_id)
        seen_hashes.append(doc_hash)
        unique.append(doc)

    return unique
