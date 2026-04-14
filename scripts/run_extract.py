"""Pass 2 extraction: extract free-text summaries from posts flagged by Pass 1.

Checkpointing: only processes classifications where pass2_needed=true and
extracted_at IS NULL. Safe to re-run — already-extracted posts are skipped.
"""

from __future__ import annotations

import logging
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from src.db import get_session, init_db
from src.extractor import extract_document, get_extract_fields
from src.models import Classification, Document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WORKERS = 20
CHUNK_SIZE = 20

_interrupted = False


def _handle_interrupt(sig, frame):
    global _interrupted
    _interrupted = True
    logger.info("Interrupt received — finishing in-flight requests then stopping.")


def _extract_one(cls_id, post_id, subreddit, title, body, extract_fields):
    """Run extraction in a thread pool worker."""
    result = extract_document(post_id, subreddit, title, body, extract_fields)
    return cls_id, result


def main():
    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    init_db()
    session = next(get_session())

    try:
        # Find pass2_needed classifications that haven't been extracted yet
        pending = (
            session.query(Classification, Document)
            .join(Document, Document.id == Classification.document_id)
            .filter(Classification.pass2_needed.is_(True))
            .filter(Classification.extracted_at.is_(None))
            .all()
        )
        total = len(pending)
        logger.info("Posts to extract: %d", total)

        # Pre-compute extraction targets
        work = []
        for cls, doc in pending:
            fields = get_extract_fields(cls.classifications)
            if not fields:
                # pass2_needed but no actual triggers — mark as done
                cls.extractions = {}
                cls.extracted_at = datetime.now(timezone.utc)
                continue
            work.append((cls.id, doc.source_id, doc.subreddit, doc.title, doc.body, fields))

        if not work:
            session.commit()
            logger.info("No extraction work to do.")
            return

        logger.info("Extraction targets: %d  (workers: %d, chunk: %d)", len(work), WORKERS, CHUNK_SIZE)

        extracted_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            for chunk_start in range(0, len(work), CHUNK_SIZE):
                if _interrupted:
                    break

                chunk = work[chunk_start : chunk_start + CHUNK_SIZE]
                futures = {
                    executor.submit(_extract_one, *item): item[0]
                    for item in chunk
                }

                for future in as_completed(futures):
                    if _interrupted:
                        break

                    cls_id, result = future.result()

                    cls_obj = session.get(Classification, cls_id)
                    if result is None:
                        failed_count += 1
                        continue

                    cls_obj.extractions = result.model_dump(exclude={"post_id"}, exclude_none=True)
                    cls_obj.extracted_at = datetime.now(timezone.utc)
                    session.commit()
                    extracted_count += 1

                logger.info(
                    "Progress: %d/%d extracted, %d failed",
                    extracted_count, len(work), failed_count,
                )

    finally:
        session.close()

    logger.info(
        "Done. Extracted: %d  Failed: %d  Remaining: %d",
        extracted_count,
        failed_count,
        len(work) - extracted_count - failed_count,
    )


if __name__ == "__main__":
    main()
