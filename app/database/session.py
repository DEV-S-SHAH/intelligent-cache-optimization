"""Database session management."""

from sqlalchemy.orm import Session
from app.database.models import engine, SessionLocal, Base


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

