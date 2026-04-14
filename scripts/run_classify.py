"""Classify unclassified documents using Gemini Flash.

Checkpointing: the database is the checkpoint. On each run, only documents
without a classification for CLASSIFIER_VERSION are processed. If the script
is interrupted (crash or Ctrl-C), restart it and it resumes from where it
left off — already-classified documents are skipped automatically.
"""

from __future__ import annotations

import logging
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.classifier import classify_document
from src.db import get_session, init_db
from src.models import Classification, Document, RawDocument

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CLASSIFIER_VERSION = "gemini_v1"
WORKERS = 20
CHUNK_SIZE = 20  # submit this many at a time, wait for all to finish, then next chunk

_interrupted = False


def _handle_interrupt(sig, frame):
    global _interrupted
    _interrupted = True
    logger.info("Interrupt received — finishing in-flight requests then stopping.")


def _classify_one(doc: Document) -> tuple[Document, object]:
    raw = RawDocument(
        source_id=doc.source_id,
        subreddit=doc.subreddit,
        author_hash=doc.author_hash,
        title=doc.title,
        body=doc.body,
        score=doc.score,
        num_comments=doc.num_comments,
        permalink=doc.permalink,
        published_at=doc.published_at,
    )
    result = classify_document(raw)
    return doc, result


def main():
    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    init_db()
    session = next(get_session())

    try:
        classified_ids = select(Classification.document_id).where(
            Classification.classifier == CLASSIFIER_VERSION
        )
        unclassified = (
            session.query(Document)
            .filter(~Document.id.in_(classified_ids))
            .order_by(Document.scraped_at.desc())
            .all()
        )
        total = len(unclassified)
        logger.info("Documents to classify: %d  (workers: %d, chunk: %d)", total, WORKERS, CHUNK_SIZE)

        classified_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            for chunk_start in range(0, total, CHUNK_SIZE):
                if _interrupted:
                    break

                chunk = unclassified[chunk_start : chunk_start + CHUNK_SIZE]
                futures = {executor.submit(_classify_one, doc): doc for doc in chunk}

                for future in as_completed(futures):
                    if _interrupted:
                        break

                    doc, result = future.result()

                    if result is None:
                        failed_count += 1
                        continue

                    classification = Classification(
                        document_id=doc.id,
                        classifier=CLASSIFIER_VERSION,
                        classifications=result.classifications.model_dump(),
                        meta=result.meta.model_dump(),
                        themes_detected_count=result.meta.themes_detected_count,
                        confidence=result.meta.confidence,
                        pass2_needed=result.meta.pass2_needed,
                        classified_at=datetime.now(timezone.utc),
                    )
                    try:
                        session.add(classification)
                        session.commit()
                        classified_count += 1
                    except IntegrityError:
                        session.rollback()

                logger.info(
                    "Progress: %d/%d classified, %d failed",
                    classified_count, total, failed_count,
                )

    finally:
        session.close()

    logger.info(
        "Done. Classified: %d  Failed: %d  Remaining: %d",
        classified_count,
        failed_count,
        total - classified_count - failed_count,
    )


if __name__ == "__main__":
    main()
