"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.models import Base

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables. For development only — use Alembic in production."""
    Base.metadata.create_all(engine)


def get_session():
    """Yield a database session, closing it when done."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
