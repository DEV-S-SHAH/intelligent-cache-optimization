import json
import logging
import os
from typing import Any, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.cache.base import BaseCache
from app.database.models import SemanticCacheEntry, get_db
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class SemanticCache(BaseCache):
    """PostgreSQL/pgvector-based semantic cache with cosine similarity."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        embedding_dim: int = 384,
        similarity_threshold: float = 0.85,
        default_ttl: Optional[int] = None,
    ):
        self.database_url = database_url or settings.database_url
        self.embedding_dim = embedding_dim
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl or settings.cache_semantic_ttl
        self._engine = create_engine(self.database_url, pool_pre_ping=True)
        self._SessionLocal = sessionmaker(bind=self._engine)
        self._pgvector_available = None

    def _check_pgvector(self) -> bool:
        if self._pgvector_available is None:
            try:
                with self._engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                self._pgvector_available = True
            except Exception as exc:
                logger.warning("pgvector extension unavailable: %s", exc)
                self._pgvector_available = False
        return self._pgvector_available

    def _generate_key(self, *parts: Any) -> str:
        import hashlib
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _row_to_entry(self, row: Any) -> dict:
        return {
            "id": row.id,
            "query_text": row.query_text,
            "embedding": row.embedding,
            "response": row.response,
            "ttl": row.ttl_seconds,
            "similarity_threshold": row.similarity_threshold,
            "hit_count": row.hit_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def search_by_similarity(
        self,
        query_embedding: List[float],
        threshold: Optional[float] = None,
        limit: int = 5,
    ) -> Optional[Tuple[dict, float]]:
        """Search cache by embedding similarity using pgvector <=> operator."""
        if not self._check_pgvector():
            return None
        threshold = threshold if threshold is not None else self.similarity_threshold
        session: Session = self._SessionLocal()
        try:
            embedding_str = ",".join(str(x) for x in query_embedding)
            sql = text(
                f"""
                SELECT id, query_text, embedding, response, ttl_seconds,
                       similarity_threshold, hit_count, created_at,
                       (embedding <=> CAST(:embedding AS vector)) AS distance
                FROM semantic_cache
                WHERE (embedding <=> CAST(:embedding AS vector)) < (1 - :threshold)
                ORDER BY distance ASC
                LIMIT :limit
                """
            )
            rows = session.execute(
                sql,
                {
                    "embedding": f"[{embedding_str}]",
                    "threshold": threshold,
                    "limit": limit,
                },
            ).fetchall()
            if not rows:
                return None
            row = rows[0]
            distance = float(row.distance)
            similarity = 1.0 - distance
            return self._row_to_entry(row), similarity
        except Exception as exc:
            logger.warning("SemanticCache search_by_similarity failed: %s", exc)
            return None
        finally:
            session.close()

    def store(
        self,
        query_text: str,
        embedding: List[float],
        response: Any,
        ttl: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> bool:
        """Store query, embedding, and response in PostgreSQL."""
        if not self._check_pgvector():
            return False
        session: Session = self._SessionLocal()
        try:
            entry_id = self._generate_key(query_text)
            embedding_str = ",".join(str(x) for x in embedding)
            sql = text(
                """
                INSERT INTO semantic_cache
                    (id, query_hash, query_text, embedding, response, ttl_seconds, similarity_threshold, hit_count)
                VALUES
                    (:id, :query_hash, :query_text, CAST(:embedding AS vector), :response, :ttl, :threshold, 0)
                ON CONFLICT (id) DO UPDATE SET
                    response = EXCLUDED.response,
                    embedding = EXCLUDED.embedding,
                    ttl_seconds = EXCLUDED.ttl_seconds,
                    similarity_threshold = EXCLUDED.similarity_threshold
                """
            )
            response_val = json.dumps(response)
            query_hash = self._generate_key(query_text)
            session.execute(
                sql,
                {
                    "id": entry_id,
                    "query_hash": query_hash,
                    "query_text": query_text,
                    "embedding": f"[{embedding_str}]",
                    "response": response_val,
                    "ttl": ttl or self.default_ttl,
                    "threshold": threshold if threshold is not None else self.similarity_threshold,
                },
            )
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("SemanticCache store failed: %s", exc)
            return False
        finally:
            session.close()

    def invalidate(self, query_text: Optional[str] = None) -> bool:
        """Invalidate cache entries, optionally filtered by query_text."""
        if not self._check_pgvector():
            return False
        session: Session = self._SessionLocal()
        try:
            if query_text:
                sql = text(
                    "DELETE FROM semantic_cache WHERE query_text = :query_text"
                )
                session.execute(sql, {"query_text": query_text})
            else:
                sql = text("TRUNCATE TABLE semantic_cache")
                session.execute(sql)
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("SemanticCache invalidate failed: %s", exc)
            return False
        finally:
            session.close()

    def get(self, key: str) -> Optional[Any]:
        """Exact lookup by generated key."""
        if not self._check_pgvector():
            return None
        session: Session = self._SessionLocal()
        try:
            sql = text("SELECT * FROM semantic_cache WHERE id = :id")
            row = session.execute(sql, {"id": key}).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)
        except Exception as exc:
            logger.warning("SemanticCache get failed: %s", exc)
            return None
        finally:
            session.close()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Not used for semantic cache; use store() instead."""
        return False

    def delete(self, key: str) -> bool:
        if not self._check_pgvector():
            return False
        session: Session = self._SessionLocal()
        try:
            sql = text("DELETE FROM semantic_cache WHERE id = :id")
            session.execute(sql, {"id": key})
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("SemanticCache delete failed: %s", exc)
            return False
        finally:
            session.close()

    def clear(self) -> None:
        self.invalidate()
