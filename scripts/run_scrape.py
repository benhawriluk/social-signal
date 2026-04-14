"""Scrape Reddit, clean, deduplicate, and store documents."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import yaml

from src.cleaner import clean_batch
from src.config import settings
from src.db import get_session, init_db
from src.dedup import compute_simhash, deduplicate
from src.models import Document
from src.scraper import scrape_subreddit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_seed_terms(path: str = "data/seed_terms.yaml") -> list[str]:
    """Load all seed terms from YAML, flattened across categories."""
    with open(path) as f:
        data = yaml.safe_load(f)
    terms: list[str] = []
    for category_terms in data.values():
        terms.extend(category_terms)
    return terms


def main():
    init_db()
    seed_terms = load_seed_terms()
    session = next(get_session())

    # Get existing source_ids to skip duplicates
    existing_ids = {row[0] for row in session.query(Document.source_id).all()}
    logger.info("Existing documents in DB: %d", len(existing_ids))

    all_docs = []
    for sub in settings.target_subreddits:
        # Newest posts
        docs = scrape_subreddit(sub, limit=settings.scrape_limit)
        all_docs.extend(docs)
        # Seed term searches
        for term in seed_terms:
            docs = scrape_subreddit(sub, query=term, limit=20)
            all_docs.extend(docs)

    logger.info("Raw scraped: %d documents", len(all_docs))

    # Clean
    cleaned = clean_batch(all_docs)
    logger.info("After cleaning: %d documents", len(cleaned))

    # Deduplicate
    unique = deduplicate(cleaned, existing_ids=existing_ids)
    logger.info("After dedup: %d new documents", len(unique))

    # Store in batches of 100
    count = 0
    for doc in unique:
        db_doc = Document(
            source_id=doc.source_id,
            subreddit=doc.subreddit,
            author_hash=doc.author_hash,
            title=doc.title,
            body=doc.body,
            parent_id=None,
            score=doc.score,
            num_comments=doc.num_comments,
            permalink=doc.permalink,
            published_at=doc.published_at,
            scraped_at=datetime.now(timezone.utc),
            word_count=len(doc.body.split()),
            simhash=compute_simhash(doc.body),
        )
        session.add(db_doc)
        count += 1

        if count % 100 == 0:
            session.commit()
            logger.info("Committed %d / %d documents", count, len(unique))

    session.commit()
    session.close()
    logger.info("Stored %d new documents", count)


if __name__ == "__main__":
    main()
