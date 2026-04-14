"""Tests for deduplication."""

from src.dedup import compute_simhash, deduplicate, simhash_distance
from src.models import RawDocument


def _make_doc(source_id: str, body: str) -> RawDocument:
    return RawDocument(source_id=source_id, subreddit="test", body=body)


class TestSimhash:
    def test_identical_texts_same_hash(self):
        h1 = compute_simhash("this is a test document about AI")
        h2 = compute_simhash("this is a test document about AI")
        assert h1 == h2

    def test_similar_texts_close_distance(self):
        base = (
            "I have been a software engineer for over twelve years now and I have to say "
            "that AI tools like ChatGPT and Copilot are making me forget how to actually "
            "write code on my own. I used to be able to sit down and bang out a function "
            "from memory but now I just ask the AI to do it for me every single time."
        )
        variant = (
            "I have been a software engineer for over twelve years now and I have to say "
            "that AI tools like ChatGPT and Copilot are making me forget how to actually "
            "write code by myself. I used to be able to sit down and bang out a function "
            "from memory but now I just ask the AI to do it for me every single time."
        )
        h1 = compute_simhash(base)
        h2 = compute_simhash(variant)
        assert simhash_distance(h1, h2) <= 5

    def test_different_texts_far_distance(self):
        h1 = compute_simhash("I love using AI tools for my work every day")
        h2 = compute_simhash("The weather in Paris is beautiful in spring time")
        assert simhash_distance(h1, h2) > 5


class TestDeduplicate:
    def test_removes_exact_id_duplicates(self):
        docs = [
            _make_doc("abc123", "first document body text here"),
            _make_doc("abc123", "first document body text here"),
        ]
        result = deduplicate(docs)
        assert len(result) == 1

    def test_removes_known_existing_ids(self):
        docs = [_make_doc("abc123", "some document body text here")]
        result = deduplicate(docs, existing_ids={"abc123"})
        assert len(result) == 0

    def test_keeps_unique_documents(self):
        docs = [
            _make_doc("a", "I feel like AI is destroying my ability to think independently"),
            _make_doc("b", "The weather in Tokyo has been unusually warm this winter season"),
        ]
        result = deduplicate(docs)
        assert len(result) == 2

    def test_removes_near_duplicates(self):
        base = (
            "I have been a software engineer for over twelve years now and I have to say "
            "that AI tools like ChatGPT and Copilot are making me forget how to actually "
            "write code on my own. I used to be able to sit down and bang out a function "
            "from memory but now I just ask the AI to do it for me every single time."
        )
        variant = (
            "I have been a software engineer for over twelve years now and I have to say "
            "that AI tools like ChatGPT and Copilot are making me forget how to actually "
            "write code by myself. I used to be able to sit down and bang out a function "
            "from memory but now I just ask the AI to do it for me every single time."
        )
        docs = [_make_doc("a", base), _make_doc("b", variant)]
        result = deduplicate(docs)
        assert len(result) == 1
