# Intelligent Cache (`intelligent-cache`)

> An intelligent caching library for LLMs, AI agents, and Python functions that **cuts API costs by up to 45%** and **returns instant responses (<1ms)** by reusing answers for identical and similar queries.

---

## What It Gives You

* 💰 **Up to 45% Cost Reduction**: Saves tokens by caching responses from OpenAI, Claude, Gemini, or custom models.
* ⚡ **Instant Speeds (<1ms)**: Automatically serves cached results for both exact matches and rephrased queries.
* 🛠️ **Universal `@cache` Decorator**: One line of code to cache any Python function (sync or async).
* 🔌 **Plug & Play Adapters**: Works seamlessly with OpenAI, Anthropic, Gemini, LangChain, and LlamaIndex.
* 📊 **Live Dashboard**: Real-time visual tracking of dollars saved, tokens saved, and hit rates.

---

## Installation

```bash
pip install intelligent-cache
```

---

## How to Use

### 1. Simple Decorator (`@cache`)

Add `@cache` above any function:

```python
from intelligent_cache import cache

@cache(ttl=3600, similarity_threshold=0.85)
def ask_ai(question: str) -> str:
    # Called only on cache misses
    return call_llm(question)

# First call: runs LLM (~500ms)
print(ask_ai("What is Kubernetes?"))

# Rephrased call: instant cache hit (<1ms, zero API cost!)
print(ask_ai("Can you explain what Kubernetes is?"))
```

### 2. Wrap LLM Clients (OpenAI, Anthropic, Gemini)

```python
# OpenAI
from openai import OpenAI
from intelligent_cache import wrap_openai

client = wrap_openai(OpenAI())
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is Python?"}]
)
```

```python
# Anthropic Claude
import anthropic
from intelligent_cache import wrap_anthropic

client = wrap_anthropic(anthropic.Anthropic())
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{"role": "user", "content": "What is Python?"}]
)
```

### 3. Direct Cache API

```python
from intelligent_cache import IntelligentCache

cache = IntelligentCache()

# Store
cache.set("What is Python?", "Python is a high-level language.")

# Retrieve (exact or similar)
result = cache.get("Tell me what Python is")
print(result.value)  # Instant response!

# Check savings
stats = cache.stats()
print(f"Cost Saved: ${stats.cost_saved_usd:.4f}")
print(f"Tokens Saved: {stats.total_tokens_saved}")
```

---

## Run Dashboard & CLI

```bash
# Windows
run.bat               # Starts API Server & Live Savings Dashboard
run.bat --dashboard   # Starts Dashboard only (http://localhost:8501)
run.bat --test        # Runs all tests

# macOS / Linux
./run.sh              # Starts API Server & Live Savings Dashboard
./run.sh --dashboard  # Starts Dashboard only (http://localhost:8501)
./run.sh --test       # Runs all tests
```

---

## License

MIT
