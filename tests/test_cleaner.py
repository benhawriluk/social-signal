"""Tests for the text cleaning pipeline."""

from src.cleaner import clean_text, scrub_pii


class TestCleanText:
    def test_strips_html(self):
        assert clean_text("<b>bold</b> text") == "bold text"

    def test_strips_reddit_quotes(self):
        result = clean_text("> quoted line\nnormal line")
        assert ">" not in result
        assert "normal line" in result

    def test_strips_markdown_bold_italic(self):
        assert clean_text("**bold** and *italic*") == "bold and italic"

    def test_strips_strikethrough(self):
        assert clean_text("~~deleted~~ text") == "deleted text"

    def test_converts_links(self):
        result = clean_text("[click here](https://example.com)")
        assert result == "click here"

    def test_normalizes_whitespace(self):
        result = clean_text("too    many   spaces")
        assert result == "too many spaces"

    def test_collapses_newlines(self):
        result = clean_text("line1\n\n\n\n\nline2")
        assert result == "line1\n\nline2"


class TestScrubPii:
    def test_removes_email(self):
        result = scrub_pii("contact me at user@example.com please")
        assert "user@example.com" not in result
        assert "[email]" in result

    def test_removes_phone(self):
        result = scrub_pii("call me at 555-123-4567")
        assert "555-123-4567" not in result
        assert "[phone]" in result

    def test_removes_url(self):
        result = scrub_pii("check https://example.com/page for details")
        assert "https://example.com" not in result
        assert "[link]" in result

    def test_preserves_normal_text(self):
        text = "I feel like AI is making me less capable"
        assert scrub_pii(text) == text
