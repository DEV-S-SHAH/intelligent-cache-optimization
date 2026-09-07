# Intelligent Caching Optimization Middleware for AI Agents

An M.Tech-level project demonstrating how intelligent multi-level caching can significantly reduce redundant LLM calls, latency, token usage, and inference costs for AI agent systems.

## Problem Statement

Modern AI agents interact with LLMs repeatedly for similar queries, leading to:
- **Redundant inference costs** — identical or paraphrased queries trigger full LLM calls
- **High latency** — LLM round-trips add 500ms–2000ms per request
- **Token waste** — repeated queries consume identical tokens
- **Scalability bottlenecks** — rate limits and API costs grow linearly with query volume

## Motivation

Caching in AI systems is often reduced to simple Redis key-value stores. This project demonstrates that **intelligent caching** — combining exact matching, semantic similarity, context awareness, tool determinism, and explainable cache policies — can optimize the trade-off between latency, cost, memory, and semantic correctness.

## Objectives

1. Design a multi-level cache middleware for AI agents
2. Implement exact, semantic, context, and tool caches
3. Build an explainable intelligent cache policy with weighted scoring
4. Demonstrate measurable latency reduction and cost savings
5. Provide quantitative benchmarking and visualization

## Architecture

```mermaid
graph LR
    A[User] --> B[AI Agent]
    B --> C[Intelligent Cache Middleware]
    C --> D{Exact Cache HIT?}
    D -->|YES| E[Return Cached]
    D -->|NO| F{Semantic Cache HIT?}
    F -->|YES| E
    F -->|NO| G{Context Cache HIT?}
    G -->|YES| E
    G -->|NO| H{Tool Cache HIT?}
    H -->|YES| E
    H -->|NO| I[LLM]
    I --> J[Intelligent Policy]
    J -->|CACHE| K[Store in All Layers]
    J -->|DO_NOT_CACHE| L[Discard]
    K --> E
    L --> E
```

### System Workflow

```text
User Query
    ↓
AI Agent
    ↓
Intelligent Cache Middleware
    ↓
┌───────────────────────────────┐
│ 1. Exact Cache (Redis)        │
│ 2. Semantic Cache (pgvector)  │
│ 3. Context Cache (PostgreSQL) │
│ 4. Tool Cache (Redis)         │
│ 5. Intelligent Policy         │
└───────────────┬───────────────┘
                │
           Cache HIT?
          /          \
        YES           NO
         ↓             ↓
    Cached Result     LLM
                       ↓
                  Store Result
                       ↓
                    Response
```

## Cache Types

### 1. Exact Cache (Redis)
- SHA256 deterministic key generation
- TTL-based expiration
- LRU-style eviction
- Hit count tracking

### 2. Semantic Cache (PostgreSQL + pgvector)
- `all-MiniLM-L6-v2` embeddings
- Cosine similarity search
- Configurable threshold (default: 0.85)
- Detects paraphrased queries

**Example:**
```text
"What is RAG?"
"Explain Retrieval Augmented Generation"
→ Semantic similarity: 0.92 → CACHE HIT
```

### 3. Context Cache (PostgreSQL)
- Session-based conversation context
- Reusable system instructions
- TTL-based context expiration

### 4. Tool Cache (Redis)
- Deterministic tool result caching
- Calculator, document lookup, weather tools
- Safe caching for idempotent operations

### 5. Intelligent Cache Policy
Explainable scoring model with configurable weights:

| Factor | Weight | Description |
|--------|--------|-------------|
| Frequency Score | 0.20 | How often query repeats |
| Similarity Score | 0.25 | Semantic similarity to cached entries |
| Recency Score | 0.15 | Time since last access |
| Reuse Probability | 0.20 | Likelihood of future reuse |
| Estimated Cost | 0.10 | LLM inference cost |
| Memory Penalty | 0.10 | Storage cost of caching |

**Decision Types:**
- `CACHE` — High score, long TTL
- `CACHE_WITH_SHORT_TTL` — Moderate score, short TTL
- `CACHE_WITH_LONG_TTL` — Borderline score, long TTL
- `DO_NOT_CACHE` — Low score, transient or low-value query

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| Caching | Redis (exact/response/context/tool) |
| Database | PostgreSQL + pgvector |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) |
| LLM | OpenAI-compatible API, Ollama, Mock provider |
| Frontend | Streamlit |
| Testing | Pytest, HTTPX |
| Visualization | Matplotlib, Plotly |
| Infrastructure | Docker Compose |

## Project Structure

```
intelligent-ai-cache/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Pydantic settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # API endpoints
│   │   └── schemas.py             # Pydantic models
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract base cache
│   │   ├── exact_cache.py         # Redis exact cache
│   │   ├── semantic_cache.py      # PostgreSQL/pgvector semantic cache
│   │   ├── context_cache.py       # PostgreSQL context cache
│   │   ├── tool_cache.py          # Redis tool result cache
│   │   ├── manager.py             # Cache orchestrator
│   │   └── policy.py              # Simple cache policy
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── scorer.py              # Intelligent cache scoring
│   │   └── eviction.py            # LRU eviction policy
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── encoder.py             # Sentence transformer encoder
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract LLM base
│   │   ├── openai_provider.py     # OpenAI-compatible provider
│   │   ├── ollama_provider.py     # Ollama provider
│   │   ├── mock_provider.py       # Mock LLM for demo
│   │   └── factory.py             # LLM provider factory
│   ├── agent/
│   │   ├── __init__.py
│   │   └── tools.py               # Deterministic agent tools
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy models
│   │   └── session.py             # DB session management
│   └── metrics/
│       ├── __init__.py
│       └── collector.py           # Performance metrics
├── dashboard/
│   ├── app.py                     # Streamlit dashboard
│   └── streamlit_app.py           # Alternative dashboard
├── scripts/
│   └── benchmark.py               # Performance benchmark
├── tests/
│   ├── __init__.py
│   ├── test_units.py              # Unit tests
│   ├── test_core.py               # Core module tests
│   └── test_api.py                # API integration tests
├── results/                       # Benchmark outputs
├── data/                          # Local data storage
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── run.sh                         # Quick start script
```

## Installation

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Redis (via Docker Compose)
- PostgreSQL with pgvector (via Docker Compose)

### Setup

```bash
# Clone the repository
cd intelligent-ai-cache

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
```

## Lightning AI Setup

Lightning AI provides managed infrastructure. Use these exact commands:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start infrastructure (if Docker available in workspace)
docker compose up -d

# 3. Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Start Streamlit dashboard (separate terminal or background)
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

### Lightning AI Without Docker

If Docker is unavailable, use SQLite fallback or managed Redis/PostgreSQL:

```bash
# Option A: Use local fallback (exact cache only, no semantic cache)
export DATABASE_URL=sqlite:///./data/cache.db
export REDIS_URL=redis://localhost:6379/0

# Option B: Use managed services
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
export REDIS_URL=redis://user:pass@host:6379/0
```

## Configuration

Edit `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=mock  # Options: mock, openai, ollama
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama2

# Embedding Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Cache TTLs (seconds)
CACHE_EXACT_TTL=3600
CACHE_SEMANTIC_TTL=86400
CACHE_CONTEXT_TTL=1800
CACHE_TOOL_TTL=7200

# Cache Policy
CACHE_SEMANTIC_THRESHOLD=0.85
CACHE_MAX_SIZE=10000
CACHE_LRU_EVICTION=true
CACHE_SCORE_THRESHOLD=0.5
CACHE_SHORT_TTL=300
CACHE_LONG_TTL=86400

# Intelligent Policy Weights
WEIGHT_FREQUENCY=0.20
WEIGHT_SIMILARITY=0.25
WEIGHT_RECENCY=0.15
WEIGHT_REUSE=0.20
WEIGHT_COST=0.10
WEIGHT_MEMORY=0.10

# Mock LLM (for demo without external API)
MOCK_LLM_DELAY_MS=1000

# Server
API_PORT=8000
DASHBOARD_PORT=8501
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

## API Usage

### Generate Response

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France?",
    "session_id": "user-123",
    "use_cache": true
  }'
```

**Response:**
```json
{
  "response": "The capital of France is Paris.",
  "cache_status": "MISS",
  "cache_type": null,
  "similarity_score": null,
  "llm_called": true,
  "latency_ms": 850
}
```

### Cache HIT Response

```json
{
  "response": "The capital of France is Paris.",
  "cache_status": "HIT",
  "cache_type": "exact",
  "similarity_score": null,
  "llm_called": false,
  "latency_ms": 12
}
```

### Semantic Cache HIT Response

```json
{
  "response": "Retrieval Augmented Generation (RAG) is...",
  "cache_status": "HIT",
  "cache_type": "semantic",
  "similarity_score": 0.92,
  "llm_called": false,
  "latency_ms": 18
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/generate` | Generate response with caching |
| GET | `/metrics` | Get performance metrics |
| GET | `/cache/stats` | Get cache statistics |
| GET | `/cache/entries` | List cached entries |
| GET | `/cache/decisions` | Recent cache policy decisions |
| DELETE | `/cache` | Clear all caches |

## Database Schema

```mermaid
erDiagram
    semantic_cache {
        string id PK
        string query_hash UK
        text query_text
        vector embedding
        json response
        float similarity_threshold
        int hit_count
        datetime created_at
        datetime last_accessed
        int ttl_seconds
        json tags
        json metadata
    }
    context_cache {
        string id PK
        string session_id
        string context_hash UK
        json context_data
        json messages
        datetime created_at
        datetime last_accessed
        int ttl_seconds
    }
    tool_cache {
        string id PK
        string tool_name
        string args_hash
        json result
        boolean is_deterministic
        datetime created_at
        datetime last_accessed
        int ttl_seconds
    }
    cache_metadata {
        string id PK
        string cache_type
        int total_size
        int max_size
        string eviction_policy
        datetime created_at
        datetime updated_at
    }
    metrics {
        string id PK
        string metric_name
        float value
        json tags
        datetime timestamp
    }
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

### Test Coverage

- Exact cache HIT/MISS
- Semantic cache HIT/MISS
- Similarity threshold enforcement
- TTL expiration
- LRU eviction
- Intelligent policy decisions
- LLM call on MISS
- No LLM call on HIT
- API endpoints
- Database operations
- Redis failure handling

## Benchmark

```bash
# Run benchmark comparing all cache modes
python scripts/benchmark.py

# With custom parameters
BENCHMARK_QUERIES=1000 BENCHMARK_SEED=42 BENCHMARK_RUNS=3 python scripts/benchmark.py
```

### Benchmark Modes

1. **No Cache** — Baseline LLM calls only
2. **Exact Cache** — Redis hash-based matching
3. **Semantic Cache** — pgvector similarity search
4. **Intelligent Multi-Level** — All layers combined with intelligent policy

### Benchmark Metrics

- Latency (avg, p50, p95)
- Hit rate
- LLM calls
- Cache hits/misses
- Tokens saved
- Estimated cost saved

### Generated Outputs

```
results/
├── benchmark_results.json
├── benchmark_results.csv
├── benchmark_report.md
└── charts/
    ├── latency_comparison.png
    ├── percentile_latency.png
    ├── cache_hit_rate.png
    ├── llm_calls.png
    ├── threshold_analysis.png
    ├── memory_efficiency.png
    └── cost_comparison.png
```

## Semantic Threshold Experiment

Test semantic thresholds to demonstrate the research aspect:

```bash
# The benchmark automatically tests thresholds: 0.75, 0.80, 0.85, 0.90, 0.95
python scripts/benchmark.py
```

### Trade-off Analysis

| Threshold | False Semantic Matches | Cache Hit Rate | Risk |
|-----------|----------------------|----------------|------|
| 0.75 | Higher | Higher | Incorrect reuse |
| 0.85 | Moderate | Moderate | Balanced |
| 0.95 | Lower | Lower | Missed opportunities |

## Dashboard

Start the Streamlit dashboard:

```bash
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

### Dashboard Features

- Real-time metrics (total requests, hit rate, latency)
- Cache type distribution pie chart
- Latency comparison bar chart
- Live query demo with cache decision visualization
- Before vs After cache comparison
- Cached entries browser (semantic, context, tool)

## Demo Workflow

```bash
# 1. Start services
docker-compose up -d

# 2. Start API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. First query — Cache MISS
curl -X POST "http://localhost:8000/generate" \
  -d '{"prompt": "What is Retrieval Augmented Generation?", "session_id": "demo"}'

# Expected:
# cache_status: MISS
# llm_called: true
# latency_ms: ~1000

# 4. Similar query — Semantic HIT
curl -X POST "http://localhost:8000/generate" \
  -d '{"prompt": "Explain Retrieval Augmented Generation.", "session_id": "demo"}'

# Expected:
# cache_status: HIT
# cache_type: semantic
# similarity_score: 0.87+
# llm_called: false
# latency_ms: ~15

# 5. Exact repeat — Exact HIT
curl -X POST "http://localhost:8000/generate" \
  -d '{"prompt": "What is Retrieval Augmented Generation?", "session_id": "demo"}'

# Expected:
# cache_status: HIT
# cache_type: exact
# llm_called: false
# latency_ms: ~15
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | LLM provider: `mock`, `openai`, `ollama` |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | OpenAI model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama server URL |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `CACHE_EXACT_TTL` | `3600` | Exact cache TTL (seconds) |
| `CACHE_SEMANTIC_TTL` | `86400` | Semantic cache TTL (seconds) |
| `CACHE_SEMANTIC_THRESHOLD` | `0.85` | Semantic similarity threshold |
| `CACHE_MAX_SIZE` | `10000` | Maximum cache entries |
| `CACHE_LRU_EVICTION` | `true` | Enable LRU eviction |
| `MOCK_LLM_DELAY_MS` | `1000` | Simulated LLM latency (ms) |

## Limitations

- Semantic cache requires pgvector extension in PostgreSQL
- Sentence transformers model download (~100MB) on first run
- Mock provider uses deterministic responses based on query hash
- Benchmark results with mock provider show simulated latency improvements
- Single-node deployment (no distributed caching)

## Future Work

- [ ] Add Redis Cluster support for distributed caching
- [ ] Implement cache warming strategies
- [ ] Add more sophisticated embedding models (e.g., OpenAI embeddings)
- [ ] Support for streaming LLM responses
- [ ] Multi-tenant cache isolation
- [ ] Advanced eviction policies (LFU, ARC)
- [ ] Cache preloading from historical data
- [ ] Integration with popular agent frameworks (LangChain, AutoGen)
- [ ] Real-time cache performance alerts
- [ ] A/B testing framework for cache strategies

## License

MIT License - M.Tech Project

## References

- [pgvector](https://github.com/pgvector/pgvector)
- [Sentence Transformers](https://www.sbert.net/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Redis](https://redis.io/)
- [Streamlit](https://streamlit.io/)
