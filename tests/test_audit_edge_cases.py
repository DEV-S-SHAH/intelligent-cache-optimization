"""Comprehensive Edge-Case & Audit Tests for Intelligent Cache Optimization.

Covers:
1. Deterministic serialization for complex objects (Pydantic, dataclasses, numpy, sets, bytes).
2. Hierarchical namespace invalidation across backends.
3. Generator streaming bypass across LLM adapters (OpenAI, Anthropic, Gemini).
4. Asynchronous adapters (LangChain alookup/aupdate/aclear, LlamaIndex chat/achat, AgentCache.step, @cache_embeddings).
5. Multi-threaded concurrency and thread safety under concurrent load.
"""

import asyncio
import dataclasses
import os
import shutil
import tempfile
import threading
import time
from typing import Any, List
import pytest
import numpy as np
from pydantic import BaseModel

from intelligent_cache.core.cache import IntelligentCache
from intelligent_cache.core.key import generate_key, generate_tool_key, generate_embedding_key, _json_serializable
from intelligent_cache.core.entry import CacheEntry
from intelligent_cache.backends.memory import MemoryBackend
from intelligent_cache.backends.sqlite import SQLiteBackend
from intelligent_cache.backends.disk import DiskBackend
from intelligent_cache.adapters.openai import wrap_openai
from intelligent_cache.adapters.anthropic import wrap_anthropic
from intelligent_cache.adapters.gemini import wrap_gemini
from intelligent_cache.adapters.langchain import IntelligentCacheLangChain
from intelligent_cache.adapters.llamaindex import IntelligentCacheLlamaIndex
from intelligent_cache.adapters.tool import AgentCache
from intelligent_cache.core.decorator import cache_embeddings


# ============================================================================
# 1. Deterministic Serialization & Complex Key Generation
# ============================================================================

class SamplePydanticModel(BaseModel):
    name: str
    score: float
    tags: List[str]


@dataclasses.dataclass
class SampleDataClass:
    user_id: int
    active: bool


def test_complex_key_serialization():
    pydantic_obj = SamplePydanticModel(name="test", score=98.5, tags=["alpha", "beta"])
    dataclass_obj = SampleDataClass(user_id=42, active=True)
    np_array = np.array([1.0, 2.0, 3.5])
    np_int = np.int64(100)
    np_float = np.float32(3.14)
    raw_set = {"b", "a", "c"}
    raw_bytes = b"hello_bytes"

    # Test _json_serializable
    assert _json_serializable(pydantic_obj)["name"] == "test"
    assert _json_serializable(dataclass_obj)["user_id"] == 42
    assert _json_serializable(np_array) == [1.0, 2.0, 3.5]
    assert _json_serializable(np_int) == 100
    assert abs(_json_serializable(np_float) - 3.14) < 1e-4
    assert _json_serializable(raw_set) == ["a", "b", "c"]
    assert _json_serializable(raw_bytes) == raw_bytes.hex()

    # Test deterministic key generation
    key1 = generate_tool_key("analyze", (pydantic_obj, np_array), {"dataset": raw_set})
    key2 = generate_tool_key("analyze", (pydantic_obj, np_array), {"dataset": {"c", "b", "a"}})
    assert key1 == key2, "Keys must be identical regardless of set iteration order"


# ============================================================================
# 2. Hierarchical Namespace Invalidation
# ============================================================================

def test_memory_hierarchical_invalidation():
    backend = MemoryBackend()
    backend.set("k1", CacheEntry(key="k1", query="q1", value="v1", namespace="tenant_1"))
    backend.set("k2", CacheEntry(key="k2", query="q2", value="v2", namespace="tenant_1:model_a"))
    backend.set("k3", CacheEntry(key="k3", query="q3", value="v3", namespace="tenant_1:model_b:v2"))
    backend.set("k4", CacheEntry(key="k4", query="q4", value="v4", namespace="tenant_2"))

    purged = backend.invalidate_namespace("tenant_1")
    assert purged == 3
    assert backend.get("k1") is None
    assert backend.get("k2") is None
    assert backend.get("k3") is None
    assert backend.get("k4") is not None


def test_sqlite_hierarchical_invalidation():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    backend = SQLiteBackend(db_path=db_path)
    try:
        backend.set("k1", CacheEntry(key="k1", query="q1", value="v1", namespace="user_10"))
        backend.set("k2", CacheEntry(key="k2", query="q2", value="v2", namespace="user_10:tools"))
        backend.set("k3", CacheEntry(key="k3", query="q3", value="v3", namespace="user_20"))

        purged = backend.invalidate_namespace("user_10")
        assert purged == 2
        assert backend.get("k1") is None
        assert backend.get("k2") is None
        assert backend.get("k3") is not None
    finally:
        backend.close()
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except Exception:
            pass


def test_disk_hierarchical_invalidation():
    temp_dir = tempfile.mkdtemp()
    try:
        backend = DiskBackend(cache_dir=temp_dir)
        backend.set("k1", CacheEntry(key="k1", query="q1", value="v1", namespace="tenant_x"))
        backend.set("k2", CacheEntry(key="k2", query="q2", value="v2", namespace="tenant_x:sub"))
        backend.set("k3", CacheEntry(key="k3", query="q3", value="v3", namespace="tenant_y"))

        purged = backend.invalidate_namespace("tenant_x")
        assert purged == 2
        assert backend.get("k1") is None
        assert backend.get("k2") is None
        assert backend.get("k3") is not None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# 3. Generator Streaming Bypass Across LLM Adapters
# ============================================================================

def test_openai_streaming_bypass():
    call_count = 0

    class MockCompletions:
        def create(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("stream"):
                return iter(["chunk1", "chunk2"])
            class MockResponse:
                usage = None
            return MockResponse()

    class MockOpenAI:
        chat = MockCompletions()
        chat.completions = MockCompletions()

    cache = IntelligentCache(backend="memory")
    client = MockOpenAI()
    wrapped = wrap_openai(client, cache_instance=cache)

    # First call with stream=True
    stream_res1 = list(wrapped.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hi"}], stream=True))
    assert stream_res1 == ["chunk1", "chunk2"]
    assert call_count == 1

    # Second call with stream=True must bypass cache and call create again
    stream_res2 = list(wrapped.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hi"}], stream=True))
    assert stream_res2 == ["chunk1", "chunk2"]
    assert call_count == 2, "Stream requests should not be cached"

    # Non-streaming call should be cached
    wrapped.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
    assert call_count == 3
    wrapped.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
    assert call_count == 3, "Non-streaming requests must be cached"


def test_anthropic_streaming_bypass():
    call_count = 0

    class MockMessages:
        def create(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("stream"):
                return iter(["claude_chunk1", "claude_chunk2"])
            class MockResponse:
                usage = None
            return MockResponse()

    class MockAnthropic:
        messages = MockMessages()

    cache = IntelligentCache(backend="memory")
    client = MockAnthropic()
    wrapped = wrap_anthropic(client, cache_instance=cache)

    # Streaming call should bypass
    list(wrapped.messages.create(model="claude-3", messages=[{"role": "user", "content": "hi"}], stream=True))
    assert call_count == 1
    list(wrapped.messages.create(model="claude-3", messages=[{"role": "user", "content": "hi"}], stream=True))
    assert call_count == 2


def test_gemini_streaming_bypass():
    call_count = 0

    class MockGeminiModel:
        model_name = "gemini-1.5"
        def generate_content(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("stream"):
                return iter(["gemini_chunk"])
            class MockResponse:
                usage_metadata = None
            return MockResponse()

    cache = IntelligentCache(backend="memory")
    model = MockGeminiModel()
    wrapped = wrap_gemini(model, cache_instance=cache)

    list(wrapped.generate_content("hello", stream=True))
    assert call_count == 1
    list(wrapped.generate_content("hello", stream=True))
    assert call_count == 2


# ============================================================================
# 4. Asynchronous Adapters & Decorators
# ============================================================================

@pytest.mark.asyncio
async def test_langchain_async_cache():
    cache = IntelligentCache(backend="memory")
    lc_cache = IntelligentCacheLangChain(cache_instance=cache, namespace="lc_test")

    # Initial lookup miss
    miss = await lc_cache.alookup(prompt="What is AI?", llm_string="gpt-4")
    assert miss is None

    # Update
    await lc_cache.aupdate(prompt="What is AI?", llm_string="gpt-4", return_val="Artificial Intelligence")

    # Second lookup hit
    hit = await lc_cache.alookup(prompt="What is AI?", llm_string="gpt-4")
    assert hit == "Artificial Intelligence"

    # Async clear
    await lc_cache.aclear()
    cleared = await lc_cache.alookup(prompt="What is AI?", llm_string="gpt-4")
    assert cleared is None


@pytest.mark.asyncio
async def test_llamaindex_async_chat_and_achat():
    call_counts = {"complete": 0, "chat": 0, "acomplete": 0, "achat": 0}

    class MockLlamaIndexLLM:
        def complete(self, prompt, **kwargs):
            call_counts["complete"] += 1
            return f"complete: {prompt}"

        async def acomplete(self, prompt, **kwargs):
            call_counts["acomplete"] += 1
            return f"acomplete: {prompt}"

        def chat(self, messages, **kwargs):
            call_counts["chat"] += 1
            return f"chat: {messages[0]['content']}"

        async def achat(self, messages, **kwargs):
            call_counts["achat"] += 1
            return f"achat: {messages[0]['content']}"

    cache = IntelligentCache(backend="memory")
    adapter = IntelligentCacheLlamaIndex(cache_instance=cache)
    llm = adapter.wrap_llm(MockLlamaIndexLLM())

    # Test sync chat
    res1 = llm.chat([{"role": "user", "content": "sync_msg"}])
    assert res1 == "chat: sync_msg"
    assert call_counts["chat"] == 1
    res2 = llm.chat([{"role": "user", "content": "sync_msg"}])
    assert res2 == "chat: sync_msg"
    assert call_counts["chat"] == 1, "Should be cached"

    # Test async achat
    ares1 = await llm.achat([{"role": "user", "content": "async_msg"}])
    assert ares1 == "achat: async_msg"
    assert call_counts["achat"] == 1
    ares2 = await llm.achat([{"role": "user", "content": "async_msg"}])
    assert ares2 == "achat: async_msg"
    assert call_counts["achat"] == 1, "Should be cached asynchronously"


@pytest.mark.asyncio
async def test_agent_cache_async_step():
    cache = IntelligentCache(backend="memory")
    agent_cache = AgentCache(cache_instance=cache)
    step_calls = 0

    @agent_cache.step("reasoning_step", inputs="problem_42")
    async def run_async_step(data: str):
        nonlocal step_calls
        step_calls += 1
        await asyncio.sleep(0.01)
        return f"result_for_{data}"

    # First call - executes
    r1 = await run_async_step("test")
    assert r1 == "result_for_test"
    assert step_calls == 1

    # Second call - cached hit
    r2 = await run_async_step("test")
    assert r2 == "result_for_test"
    assert step_calls == 1


@pytest.mark.asyncio
async def test_async_cache_embeddings():
    cache = IntelligentCache(backend="memory")
    emb_calls = 0

    @cache_embeddings(cache_instance=cache, model_name="text-embedding-3-small")
    async def get_embedding_async(text: str) -> list:
        nonlocal emb_calls
        emb_calls += 1
        await asyncio.sleep(0.01)
        return [0.1, 0.2, 0.3]

    vec1 = await get_embedding_async("deep learning")
    assert vec1 == [0.1, 0.2, 0.3]
    assert emb_calls == 1

    vec2 = await get_embedding_async("deep learning")
    assert vec2 == [0.1, 0.2, 0.3]
    assert emb_calls == 1, "Async embedding must be retrieved from cache"


# ============================================================================
# 5. Multi-Threaded Concurrency & Lock Stress Test
# ============================================================================

def test_multithreaded_concurrency_stress():
    cache = IntelligentCache(backend="memory")
    num_threads = 10
    ops_per_thread = 50
    errors = []

    def worker(thread_id: int):
        try:
            for i in range(ops_per_thread):
                key = f"key_{thread_id % 3}_{i % 5}"
                cache.set(key, f"val_{thread_id}_{i}")
                val = cache.get(key)
                assert val is not None
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent operations raised errors: {errors}"
    metrics = cache.metrics.summary()
    assert metrics["total_requests"] > 0
