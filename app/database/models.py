"""Database models and session management."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean,
    DateTime, Text, JSON, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy import String
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER','postgres')}:{os.getenv('POSTGRES_PASSWORD','postgres')}"
    f"@{os.getenv('POSTGRES_HOST','localhost')}:{os.getenv('POSTGRES_PORT','5432')}"
    f"/{os.getenv('POSTGRES_DB','cache_db')}"
)

Base = declarative_base()


class SemanticCacheEntry(Base):
    """Stores semantic cache entries with embeddings."""
    __tablename__ = "semantic_cache"

    id = Column(String, primary_key=True)
    query_hash = Column(String(64), unique=True, nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=True)
    response = Column(JSON, nullable=False)
    similarity_threshold = Column(Float, default=0.85)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ttl_seconds = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)


class ContextCacheEntry(Base):
    """Stores conversation/session context cache."""
    __tablename__ = "context_cache"

    id = Column(String, primary_key=True)
    session_id = Column(String(128), nullable=False, index=True)
    context_hash = Column(String(64), unique=True, nullable=False, index=True)
    context_data = Column(JSON, nullable=False)
    messages = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ttl_seconds = Column(Integer, nullable=True)


class ToolCacheEntry(Base):
    """Stores tool result cache."""
    __tablename__ = "tool_cache"

    id = Column(String, primary_key=True)
    tool_name = Column(String(128), nullable=False, index=True)
    args_hash = Column(String(64), nullable=False, index=True)
    result = Column(JSON, nullable=False)
    is_deterministic = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ttl_seconds = Column(Integer, nullable=True)


class CacheMetadata(Base):
    """Stores cache management metadata."""
    __tablename__ = "cache_metadata"

    id = Column(String, primary_key=True)
    cache_type = Column(String(50), nullable=False)
    total_size = Column(Integer, default=0)
    max_size = Column(Integer, default=10000)
    eviction_policy = Column(String(50), default="lru")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Metric(Base):
    """Stores time-series metrics."""
    __tablename__ = "metrics"

    id = Column(String, primary_key=True)
    metric_name = Column(String(128), nullable=False, index=True)
    value = Column(Float, nullable=False)
    tags = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# Engine setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


CachedResponse = SemanticCacheEntry
