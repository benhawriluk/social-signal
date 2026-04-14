"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Reddit (no API key needed — uses public JSON endpoints)
    reddit_user_agent: str = "social-signal/0.1.0 (research project)"

    # Database
    database_url: str = "postgresql://localhost:5432/social_signal"

    # OpenRouter
    openrouter_api_key: str = ""
    classifier_model: str = "google/gemini-3-flash-preview"

    # Scraper defaults
    target_subreddits: list[str] = [
        "ChatGPT",
        "ExperiencedDevs",
        "teachers",
        "replika",
        "singularity",
    ]
    min_text_length: int = 50
    scrape_limit: int = 100  # posts per subreddit per run

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
