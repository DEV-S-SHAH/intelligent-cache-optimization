import json
import logging
import os
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.cache.base import BaseCache
from app.database.models import ContextCacheEntry
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ContextCache(BaseCache):
    """PostgreSQL context cache for session/conversation context."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        default_ttl: Optional[int] = None,
    ):
        self.database_url = database_url or settings.database_url
        try:
            self._engine = create_engine(self.database_url, pool_pre_ping=True)
            self._engine.dialect.dbapi
        except Exception:
            self._engine = create_engine("sqlite:///cache_fallback.db")
        self._SessionLocal = sessionmaker(bind=self._engine)

    def _generate_key(self, *parts: Any) -> str:
        import hashlib
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        session: Session = self._SessionLocal()
        try:
            sql = text(
                """
                SELECT id, session_id, context_data, messages, ttl_seconds, created_at, last_accessed
                FROM context_cache
                WHERE id = :id
                """
            )
            row = session.execute(sql, {"id": key}).fetchone()
            if row is None:
                return None
            return {
                "id": row.id,
                "session_id": row.session_id,
                "context_data": row.context_data,
                "messages": row.messages,
                "ttl_seconds": row.ttl_seconds,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_accessed": row.last_accessed.isoformat() if row.last_accessed else None,
            }
        except Exception as exc:
            logger.warning("ContextCache get failed: %s", exc)
            return None
        finally:
            session.close()

    def get_by_session(self, session_id: str) -> Optional[Any]:
        """Retrieve context by session_id."""
        key = self._generate_key("session", session_id)
        return self.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        session: Session = self._SessionLocal()
        try:
            context_data = value if isinstance(value, dict) else {"data": value}
            messages = context_data.get("messages", [])
            sql = text(
                """
                INSERT INTO context_cache
                    (id, session_id, context_hash, context_data, messages, ttl_seconds)
                VALUES
                    (:id, :session_id, :context_hash, :context_data, :messages, :ttl)
                ON CONFLICT (id) DO UPDATE SET
                    context_data = EXCLUDED.context_data,
                    messages = EXCLUDED.messages,
                    ttl_seconds = EXCLUDED.ttl_seconds
                """
            )
            session_id = context_data.get("session_id", key)
            context_hash = self._generate_key("session", session_id)
            session.execute(
                sql,
                {
                    "id": key,
                    "session_id": session_id,
                    "context_hash": context_hash,
                    "context_data": json.dumps(context_data),
                    "messages": json.dumps(messages),
                    "ttl": ttl or self.default_ttl,
                },
            )
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("ContextCache set failed: %s", exc)
            return False
        finally:
            session.close()

    def set_context(
        self,
        session_id: str,
        context_data: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        key = self._generate_key("session", session_id)
        if isinstance(context_data, dict):
            context_data.setdefault("session_id", session_id)
        else:
            context_data = {"session_id": session_id, "data": context_data}
        return self.set(key, context_data, ttl=ttl)

    def append_message(self, session_id: str, message: Any) -> bool:
        """Append a message to an existing session context."""
        key = self._generate_key("session", session_id)
        session: Session = self._SessionLocal()
        try:
            sql = text(
                """
                SELECT context_data, messages
                FROM context_cache
                WHERE id = :id
                """
            )
            row = session.execute(sql, {"id": key}).fetchone()
            if row is None:
                logger.warning("ContextCache append_message: session %s not found", session_id)
                return False
            context_data = row.context_data or {}
            messages = row.messages or []
            if isinstance(messages, str):
                messages = json.loads(messages)
            messages.append(message)
            update_sql = text(
                """
                UPDATE context_cache
                SET messages = :messages
                WHERE id = :id
                """
            )
            session.execute(update_sql, {"messages": json.dumps(messages), "id": key})
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("ContextCache append_message failed: %s", exc)
            return False
        finally:
            session.close()

    def delete(self, key: str) -> bool:
        session: Session = self._SessionLocal()
        try:
            sql = text("DELETE FROM context_cache WHERE id = :id")
            session.execute(sql, {"id": key})
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.warning("ContextCache delete failed: %s", exc)
            return False
        finally:
            session.close()

    def clear(self) -> None:
        session: Session = self._SessionLocal()
        try:
            sql = text("TRUNCATE TABLE context_cache")
            session.execute(sql)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("ContextCache clear failed: %s", exc)
        finally:
            session.close()
