"""Key generation and normalization utilities."""

import hashlib
import json
from typing import Any, Optional


def normalize_query(query: str) -> str:
    """Normalize query text for deterministic exact matching.
    
    Lowers casing and collapses consecutive whitespace.
    """
    if not isinstance(query, str):
        query = str(query)
    normalized = " ".join(query.lower().strip().split())
    return normalized


def _json_serializable(obj: Any) -> Any:
    """Helper to convert arbitrary objects to JSON serializable structures deterministically."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return obj.item()
        except Exception:
            pass
    if hasattr(obj, "tolist") and callable(obj.tolist):
        try:
            return _json_serializable(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return _json_serializable(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return _json_serializable(obj.dict())
        except Exception:
            pass
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        try:
            return _json_serializable(dataclasses.asdict(obj))
        except Exception:
            pass
    if isinstance(obj, (set, frozenset)):
        return sorted([_json_serializable(item) for item in obj], key=lambda x: str(x))
    if isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    if isinstance(obj, (list, tuple)):
        return [_json_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _json_serializable(v) for k, v in sorted(obj.items(), key=lambda item: str(item[0]))}
    if hasattr(obj, "__dict__"):
        return _json_serializable(vars(obj))
    return str(obj)


def generate_key(
    query: str,
    namespace: str = "default",
    extra_params: Optional[dict[str, Any]] = None,
) -> str:
    """Generate a deterministic SHA-256 cache key for a query."""
    normalized = normalize_query(query)
    payload: dict[str, Any] = {
        "ns": namespace,
        "q": normalized,
    }
    if extra_params:
        payload["extra"] = _json_serializable(extra_params)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest[:32]}"


def generate_tool_key(
    tool_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    namespace: str = "tools",
) -> str:
    """Generate a deterministic cache key for an agent tool or function call."""
    payload = {
        "tool": tool_name,
        "args": _json_serializable(args),
        "kwargs": _json_serializable(kwargs),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{namespace}:{tool_name}:{digest[:32]}"


def generate_embedding_key(text: str, model_name: str = "default") -> str:
    """Generate a cache key for embedding vectors."""
    payload = {
        "model": model_name,
        "text": text,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"emb:{model_name}:{digest[:32]}"
