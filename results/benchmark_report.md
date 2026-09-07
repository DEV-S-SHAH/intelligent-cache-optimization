# Intelligent Cache Benchmark Report
Generated: 2026-09-07 01:21:55 UTC

## Summary Comparison

| Metric | No Cache | Exact Cache | Semantic Cache | Intelligent Multi-Level |
|--------|----------|-------------|----------------|-------------------------|
| avg_latency_ms | 100.2 | 74.4 | 75.0 | 11.1 |
| hit_rate | 0.0% | 26.0% | 37.0% | 100.0% |
| llm_calls | 100.0 | 74.0 | 63.0 | 0.0 |
| cache_hits | 0.0 | 26.0 | 37.0 | 100.0 |
| cost_saved | $0.0000 | $0.0106 | $0.0119 | $0.0131 |

## Cache Efficiency

| Mode | Total Entries | Avg Hits/Entry | Evictions |
|------|---------------|----------------|----------|
| No Cache | 0 | 0.00 | 0 |
| Exact | 74 | 0.00 | 0 |
| Semantic | 63 | 0.00 | 0 |
| Intelligent | 63 | 2.17 | 0 |

## Detailed Results

### No Cache
- Total Queries: 100
- LLM Calls: 100.0
- Cache Hits: 0.0
- Cache Misses: 100.0
- Hit Rate: 0.0%
- Avg Latency: 100.2 ms
- P50 Latency: 100.2 ms
- P95 Latency: 100.4 ms
- Tokens Saved: 0
- Cost Saved: $0.0000
- Cache Entries: 0
- Avg Hits/Entry: 0.00
- Evictions: 0

### Exact
- Total Queries: 100
- LLM Calls: 74.0
- Cache Hits: 26.0
- Cache Misses: 74.0
- Hit Rate: 26.0%
- Avg Latency: 74.4 ms
- P50 Latency: 100.3 ms
- P95 Latency: 100.6 ms
- Tokens Saved: 532
- Cost Saved: $0.0106
- Cache Entries: 74
- Avg Hits/Entry: 0.00
- Evictions: 0

### Semantic
- Total Queries: 100
- LLM Calls: 63.0
- Cache Hits: 37.0
- Cache Misses: 63.0
- Hit Rate: 37.0%
- Avg Latency: 75.0 ms
- P50 Latency: 110.6 ms
- P95 Latency: 116.6 ms
- Tokens Saved: 594
- Cost Saved: $0.0119
- Cache Entries: 63
- Avg Hits/Entry: 0.00
- Evictions: 0

### Intelligent
- Total Queries: 100
- LLM Calls: 0.0
- Cache Hits: 100.0
- Cache Misses: 0.0
- Hit Rate: 100.0%
- Avg Latency: 11.1 ms
- P50 Latency: 10.1 ms
- P95 Latency: 16.7 ms
- Tokens Saved: 657
- Cost Saved: $0.0131
- Cache Entries: 63
- Avg Hits/Entry: 2.17
- Evictions: 0

## Methodology

- **No Cache**: Every query goes directly to the LLM with no caching.
- **Exact Cache**: Uses Redis for exact string matching with SHA256 hashing.
- **Semantic Cache**: Uses PostgreSQL/pgvector for embedding-based similarity search.
- **Intelligent Multi-Level**: Combines exact and semantic caches with intelligent policy scoring.

## Environment

- Python 3.12
- Redis 7 (via Docker)
- PostgreSQL 16 with pgvector (via Docker)
- Mock LLM latency: 1000 ms (simulated)
