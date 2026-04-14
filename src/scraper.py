"""Reddit scraper using public JSON endpoints (no API key needed)."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from src.config import settings
from src.models import RawDocument

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": settings.reddit_user_agent}
REQUEST_DELAY = 3.0  # seconds between requests — Reddit throttles aggressively without API key


def _hash_author(username: str | None) -> str | None:
    if not username or username == "[deleted]":
        return None
    return hashlib.sha256(username.encode()).hexdigest()


def _fetch_json(url: str) -> dict | None:
    """Fetch a Reddit JSON endpoint with rate limiting and error handling."""
    try:
        time.sleep(REQUEST_DELAY)
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            logger.warning("Rate limited, sleeping %ds", retry_after)
            time.sleep(retry_after)
            resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None


def _parse_post(post_data: dict, subreddit_name: str) -> RawDocument | None:
    """Parse a Reddit post JSON object into a RawDocument."""
    data = post_data.get("data", post_data)

    body = data.get("selftext", "")
    title = data.get("title", "")
    if not body and title:
        body = title

    if len(body) < settings.min_text_length:
        return None

    created = data.get("created_utc")
    published_at = datetime.fromtimestamp(created, tz=timezone.utc) if created else None

    return RawDocument(
        source_id=data.get("id", ""),
        subreddit=subreddit_name,
        author_hash=_hash_author(data.get("author")),
        title=title,
        body=body,
        score=data.get("score"),
        num_comments=data.get("num_comments"),
        permalink=f"https://reddit.com{data['permalink']}" if data.get("permalink") else None,
        published_at=published_at,
    )


def _parse_comment(comment_data: dict, subreddit_name: str, post_id: str) -> RawDocument | None:
    """Parse a Reddit comment JSON object into a RawDocument."""
    data = comment_data.get("data", comment_data)

    body = data.get("body", "")
    if len(body) < settings.min_text_length:
        return None

    created = data.get("created_utc")
    published_at = datetime.fromtimestamp(created, tz=timezone.utc) if created else None

    return RawDocument(
        source_id=data.get("id", ""),
        subreddit=subreddit_name,
        author_hash=_hash_author(data.get("author")),
        title=None,
        body=body,
        parent_id=post_id,
        score=data.get("score"),
        permalink=f"https://reddit.com{data['permalink']}" if data.get("permalink") else None,
        published_at=published_at,
    )


def scrape_subreddit(
    subreddit_name: str,
    query: str | None = None,
    limit: int | None = None,
) -> list[RawDocument]:
    """Scrape posts from a subreddit using Reddit's public JSON endpoints.

    Uses https://www.reddit.com/r/{sub}/new.json or
    https://www.reddit.com/r/{sub}/search.json?q={query}&sort=new
    """
    limit = limit or settings.scrape_limit
    docs: list[RawDocument] = []

    if query:
        encoded_q = quote_plus(query)
        url = f"https://www.reddit.com/r/{subreddit_name}/search.json?q={encoded_q}&sort=new&restrict_sr=on&limit={limit}"
    else:
        url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit={limit}"

    result = _fetch_json(url)
    if not result:
        return docs

    children = result.get("data", {}).get("children", [])
    for child in children:
        doc = _parse_post(child.get("data", {}), subreddit_name)
        if doc:
            docs.append(doc)

    logger.info("Scraped %d posts from r/%s (query=%s)", len(docs), subreddit_name, query)
    return docs


def scrape_comments(
    subreddit_name: str,
    post_id: str,
) -> list[RawDocument]:
    """Scrape comments from a specific post."""
    url = f"https://www.reddit.com/r/{subreddit_name}/comments/{post_id}.json?limit=200"
    docs: list[RawDocument] = []

    result = _fetch_json(url)
    if not result or not isinstance(result, list) or len(result) < 2:
        return docs

    # result[1] contains the comment listing
    comments = result[1].get("data", {}).get("children", [])
    for child in comments:
        if child.get("kind") != "t1":
            continue
        doc = _parse_comment(child.get("data", {}), subreddit_name, post_id)
        if doc:
            docs.append(doc)

    logger.info("Scraped %d comments from r/%s post %s", len(docs), subreddit_name, post_id)
    return docs


def scrape_all(queries: list[str]) -> list[RawDocument]:
    """Run all seed queries across all target subreddits."""
    all_docs: list[RawDocument] = []
    for sub in settings.target_subreddits:
        # Fetch newest posts
        all_docs.extend(scrape_subreddit(sub))
        # Search each seed query
        for q in queries:
            all_docs.extend(scrape_subreddit(sub, query=q))
    logger.info("Total scraped: %d documents", len(all_docs))
    return all_docs
