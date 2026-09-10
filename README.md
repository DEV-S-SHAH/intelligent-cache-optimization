# Intelligent Cache (`intelligent-cache`)

[![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://pypi.org/project/intelligent-cache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-79%2F79%20passing-brightgreen.svg)]()
[![Platform: Windows & macOS](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg)]()

> **⚡ What is this project about?**
> **Intelligent Cache** is a model-agnostic caching optimization library for LLMs, AI Agents, and Vector APIs. It **cuts inference costs by up to 45%** and **reduces response times from ~500ms to 0.2ms** by serving instant answers for repeated and semantically similar queries.
>
> It works **out-of-the-box with zero external dependencies** (runs in-memory or on SQLite) and scales seamlessly to **Redis** and **PostgreSQL / pgvector**.

---

## 🚀 Key Features

* **Multi-Tier Caching**:
  * **Tier 1 (Exact Match, ~0.1ms)**: SHA-256 hash lookup for identical prompts.
  * **Tier 2 (Semantic Similarity, ~0.2ms)**: Cosine vector similarity for paraphrased questions (*"What's the capital of France?"* matches *"Tell me France's capital"*).
  * **Tier 3 (Agent Tools & Steps)**: Deduplicates deterministic calculations, API tools, and agent planning steps.
  * **Tier 4 (Vector Embeddings)**: Caches raw embedding vectors to avoid duplicate embedding API calls.
* **Universal Decorator (`@cache`)**: Wrap any sync or async Python function with a single line.
* **Pluggable Storage Backends**: In-Memory (LRU/LFU/FIFO), SQLite (zero-config persistent disk), Filesystem, Redis, PostgreSQL/pgvector.
* **Model & Framework Agnostic**: Drop-in adapters for **OpenAI**, **Anthropic Claude**, **Google Gemini**, **LangChain**, and **LlamaIndex**.
* **5-Dimensional Invalidation**: Purge by exact query, namespace partition, tag label, or semantic radius.
* **Interactive Dashboard**: Real-time tracking of **Cost Saved ($)**, **Tokens Saved**, and **Latency Saved (s)**.

---

## 📦 Installation

```bash
# Install as a library:
pip install intelligent-cache

# Or install from local source:
pip install -e .

# Or build distributable wheels:
python -m build
pip install dist/intelligent_cache-1.0.0-py3-none-any.whl

# Optional backends & integrations:
pip install intelligent-cache[redis,postgres,openai,anthropic,langchain]
```

---

## ⚡ 30-Second Quickstart

```python
from intelligent_cache import IntelligentCache, cache

# 1. Direct Client Usage (In-Memory or SQLite)
cache_client = IntelligentCache(similarity_threshold=0.82)
cache_client.set("What is Python?", "Python is a high-level programming language.")

# Exact Match (~0.1ms)
res1 = cache_client.get("What is Python?")
print(res1.value, res1.hit_type)  # "Python is...", CacheHitType.EXACT

# Semantic Match (~0.2ms) - Rephrased query automatically detected!
res2 = cache_client.get("Can you explain what Python is?")
print(res2.value, res2.similarity_score)  # "Python is...", 0.8942 (CacheHitType.SEMANTIC)

# 2. Universal Decorator Usage
@cache(ttl=3600, similarity_threshold=0.82)
def ask_ai(question: str) -> str:
    return call_llm(question)  # Only invoked on cache misses
```

---

## 💻 Cross-Platform Execution (Windows & macOS)

The project includes native one-click launchers for both **Windows** and **macOS / Linux**:

### On Windows (Command Prompt or PowerShell):
```cmd
run.bat --check             :: Verify Python and dependencies
run.bat --test              :: Run 79/79 test suite
run.bat --evaluate-docs     :: Run PDF & Text document QA evaluation
run.bat --benchmark         :: Run comparative benchmark
run.bat                     :: Launch FastAPI (:8000) & Streamlit Dashboard (:8501)
```

### On macOS & Linux:
```bash
chmod +x run.sh
./run.sh --check            # Verify Python and dependencies
./run.sh --test             # Run 79/79 test suite
./run.sh --evaluate-docs    # Run PDF & Text document QA evaluation
./run.sh --benchmark        # Run comparative benchmark
./run.sh                    # Launch FastAPI (:8000) & Streamlit Dashboard (:8501)
```

### Unified CLI Options (`python run.py`):
| Flag | Description |
|---|---|
| `python run.py` | Starts both FastAPI REST API (`:8000`) and Streamlit Dashboard (`:8501`) |
| `python run.py --dashboard` | Starts only the interactive savings dashboard (`:8501`) |
| `python run.py --api` | Starts only the FastAPI REST service (`:8000`) |
| `python run.py --evaluate-docs` | Runs automated evaluations across PDF and text policies |
| `python run.py --benchmark` | Runs comparative benchmark (No Cache vs Exact vs Semantic) |
| `python run.py --test` | Runs full test suite (79 tests passing) |
| `python run.py --check` | Runs environment and health diagnostics |

---

## 📊 Interactive Savings Dashboard

Run `python run.py --dashboard` to open the Streamlit interface (`http://localhost:8501`):

* **Hero Savings KPIs**: Live tracking of **Cost Saved ($)**, **Tokens Saved**, **Latency Saved (s)**, and **Hit Rate (%)**.
* **Interactive Query Tester**: Test queries with immediate feedback on hit tier, similarity score, and speedup.
* **Document QA Studio**: Select `sample_policy.pdf` or text documents, test questions, and run benchmark evaluations.
* **Zero-Setup Standalone Mode**: Works immediately in-process even if the FastAPI server is offline.

---

## 📄 PDF & Text Document Evaluations

Automated chunking and semantic retrieval evaluation over enterprise policies (`data/sample_policy.pdf`, `data/security_policy.txt`, `data/expense_policy.txt`):

```bash
python run.py --evaluate-docs
```

### Evaluation Benchmark Results:
| Metric | Without Cache | Traditional Exact Cache | Intelligent Semantic Cache |
|---|---|---|---|
| **Total Query Time** | `6.74s` | `5.52s` | **`4.23s`** |
| **Mean Latency** | `421.1ms` | `344.6ms` | **`264.5ms`** |
| **Hit Rate** | `0.0%` | `18.8%` | **`37.5%`** |
| **Exact Hits** | `0` | `3` | `3` |
| **Semantic Hits** | `0` | `0` | **`3`** |
| **Speedup Factor** | `1.0x (baseline)` | `1.22x` | **`1.59x`** |

> **Key Takeaway**: Exact-only caching completely misses rephrased user queries. The Intelligent Semantic Cache captures the semantic intent, providing **1.59x faster retrieval** and **37.5% hit rate**.

---

## 🔌 Framework & LLM Adapters

Drop-in compatibility with popular AI ecosystems:

```python
# OpenAI
from openai import OpenAI
from intelligent_cache import wrap_openai, IntelligentCache
client = wrap_openai(OpenAI(), cache_instance=IntelligentCache())

# Anthropic Claude
import anthropic
from intelligent_cache import wrap_anthropic
client = wrap_anthropic(anthropic.Anthropic())

# LangChain Global Cache
from langchain.globals import set_llm_cache
from intelligent_cache import IntelligentCache, IntelligentCacheLangChain
set_llm_cache(IntelligentCacheLangChain(IntelligentCache()))

# Agent Step & Planning Caching
from intelligent_cache import AgentCache
agent_cache = AgentCache()
@agent_cache.step("planning")
def generate_plan(goal): ...
```

---

## 🧪 Testing

```bash
pytest tests/ -v
```
Output:
```text
======================== 79 passed in 1.62s ========================
```

---

## 📄 License

MIT License. Designed for production AI agent optimization.

