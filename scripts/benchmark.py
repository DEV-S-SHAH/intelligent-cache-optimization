"""Benchmark script to evaluate cache performance."""

import os
import sys
import time
import json
import hashlib
import random
import string
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from app.llm.factory import get_llm
from app.cache.manager import CacheManager
from app.metrics.collector import MetricsCollector
from app.embeddings.encoder import EmbeddingEncoder
from app.agent.tools import AgentTools
from app.benchmark.workload import generate_workload, save_workload as save_workload_csv


def generate_synthetic_queries(num_queries: int = 1000) -> List[Dict[str, Any]]:
    """Generate realistic mixed workload for benchmarking."""
    return generate_workload(num_queries)


def run_benchmark(
    mode: str,
    queries: List[Dict[str, Any]],
    llm,
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
    semantic_threshold: float = 0.85,
) -> Dict[str, Any]:
    """Run benchmark in a specific mode."""
    results = {
        "mode": mode,
        "semantic_threshold": semantic_threshold,
        "queries": [],
        "total_queries": len(queries),
        "llm_calls": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "exact_hits": 0,
        "semantic_hits": 0,
        "tool_hits": 0,
        "context_hits": 0,
        "total_latency_ms": 0.0,
        "latencies": [],
        "tokens_saved": 0,
        "cost_saved": 0.0,
        "start_time": datetime.utcnow().isoformat(),
        "cache_decisions": [],
        "cache_efficiency": {
            "total_entries": 0,
            "unique_entries": 0,
            "evictions": 0,
            "expired_entries": 0,
            "avg_hits_per_entry": 0.0,
        },
    }

    for i, query_data in enumerate(queries):
        query_text = query_data["text"]
        query_type = query_data["type"]
        start = time.time()

        try:
            if mode == "no_cache":
                response = llm.generate(query_text)
                latency_ms = (time.time() - start) * 1000
                results["llm_calls"] += 1
                results["cache_misses"] += 1
                metrics.record_miss()

            elif mode == "exact_cache":
                key = cache_manager.exact._generate_key(query_text)
                cached = cache_manager.exact.get(key)
                if cached is not None:
                    response = cached
                    latency_ms = (time.time() - start) * 1000
                    results["cache_hits"] += 1
                    results["exact_hits"] += 1
                    metrics.record_hit("exact")
                else:
                    response = llm.generate(query_text)
                    latency_ms = (time.time() - start) * 1000
                    cache_manager.exact.set(key, response)
                    results["llm_calls"] += 1
                    results["cache_misses"] += 1
                    metrics.record_miss()

            elif mode == "semantic_cache":
                embedding = encoder.encode(query_text)
                hit = cache_manager.semantic.search_by_similarity(
                    embedding, threshold=semantic_threshold
                )
                if hit is not None:
                    entry, similarity = hit
                    response = entry.get("response")
                    latency_ms = (time.time() - start) * 1000
                    results["cache_hits"] += 1
                    results["semantic_hits"] += 1
                    metrics.record_hit("semantic")
                else:
                    response = llm.generate(query_text)
                    latency_ms = (time.time() - start) * 1000
                    cache_manager.semantic.store(
                        query_text, embedding, response, threshold=semantic_threshold
                    )
                    results["llm_calls"] += 1
                    results["cache_misses"] += 1
                    metrics.record_miss()

            else:  # intelligent_multi_level
                embedding = encoder.encode(query_text)
                cache_result = cache_manager.get(query_text, context=embedding)

                if cache_result is not None:
                    response = cache_result.get("response", "")
                    latency_ms = (time.time() - start) * 1000
                    results["cache_hits"] += 1
                    if cache_result.get("cache_type") == "exact":
                        results["exact_hits"] += 1
                        metrics.record_hit("exact")
                    elif cache_result.get("cache_type") == "semantic":
                        results["semantic_hits"] += 1
                        metrics.record_hit("semantic")
                else:
                    response = llm.generate(query_text)
                    latency_ms = (time.time() - start) * 1000
                    policy = cache_manager.set(query_text, response, context=embedding)
                    results["llm_calls"] += 1
                    results["cache_misses"] += 1
                    results["cache_decisions"].append(policy)
                    metrics.record_miss()

            results["total_latency_ms"] += latency_ms
            results["latencies"].append(latency_ms)
            results["queries"].append({
                "text": query_text[:60],
                "type": query_type,
                "latency_ms": round(latency_ms, 2),
            })

            if mode != "no_cache" and results["cache_hits"] > 0:
                estimated_tokens = len(query_text.split()) * 1.3
                results["tokens_saved"] += estimated_tokens
                results["cost_saved"] += estimated_tokens * 0.00002

        except Exception as e:
            print(f"Error processing query '{query_text[:30]}...': {e}")
            results["latencies"].append(0)

    results["end_time"] = datetime.utcnow().isoformat()
    if results["latencies"]:
        results["avg_latency_ms"] = float(np.mean(results["latencies"]))
        results["p50_latency_ms"] = float(np.percentile(results["latencies"], 50))
        results["p95_latency_ms"] = float(np.percentile(results["latencies"], 95))
        results["min_latency_ms"] = float(np.min(results["latencies"]))
        results["max_latency_ms"] = float(np.max(results["latencies"]))
    else:
        results["avg_latency_ms"] = 0.0
        results["p50_latency_ms"] = 0.0
        results["p95_latency_ms"] = 0.0
        results["min_latency_ms"] = 0.0
        results["max_latency_ms"] = 0.0

    results["hit_rate"] = results["cache_hits"] / len(queries) if queries else 0.0

    stats = cache_manager.stats()
    results["cache_efficiency"] = {
        "total_entries": stats.get("total_entries", 0),
        "unique_entries": stats.get("total_entries", 0),
        "evictions": stats.get("evictions", 0),
        "expired_entries": stats.get("expired_entries", 0),
        "avg_hits_per_entry": stats.get("avg_hits_per_entry", 0.0),
        "decision_distribution": stats.get("cache_decision_distribution", {}),
    }

    return results


def print_results(results: Dict[str, Any]):
    """Print benchmark results."""
    print(f"\n{'='*60}")
    print(f"Mode: {results['mode']} (threshold={results.get('semantic_threshold', 'N/A')})")
    print(f"{'='*60}")
    print(f"Total Queries:     {results['total_queries']}")
    print(f"LLM Calls:         {results['llm_calls']}")
    print(f"Cache Hits:        {results['cache_hits']}")
    print(f"Cache Misses:      {results['cache_misses']}")
    print(f"Hit Rate:          {results['hit_rate']:.1%}")
    print(f"Avg Latency:       {results['avg_latency_ms']:.1f} ms")
    print(f"P50 Latency:       {results['p50_latency_ms']:.1f} ms")
    print(f"P95 Latency:       {results['p95_latency_ms']:.1f} ms")
    print(f"Min Latency:       {results['min_latency_ms']:.1f} ms")
    print(f"Max Latency:       {results['max_latency_ms']:.1f} ms")
    print(f"Total Latency:     {results['total_latency_ms']:.1f} ms")
    print(f"Tokens Saved:      {results['tokens_saved']:.0f}")
    print(f"Cost Saved:        ${results['cost_saved']:.4f}")
    eff = results.get("cache_efficiency", {})
    print(f"Cache Entries:     {eff.get('total_entries', 0)}")
    print(f"Avg Hits/Entry:    {eff.get('avg_hits_per_entry', 0.0):.2f}")
    print(f"Evictions:         {eff.get('evictions', 0)}")
    print(f"{'='*60}\n")


def save_results(all_results: Dict[str, Dict[str, Any]], output_dir: str):
    """Save benchmark results in multiple formats."""
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "benchmark_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"JSON saved: {json_path}")

    csv_path = os.path.join(output_dir, "benchmark_results.csv")
    modes = ["no_cache", "exact_cache", "semantic_cache", "intelligent_multi_level"]
    mode_labels = ["No Cache", "Exact", "Semantic", "Intelligent"]

    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("mode,avg_latency_ms,p50_latency_ms,p95_latency_ms,hit_rate,llm_calls,cache_hits,cache_misses,cost_saved,total_entries,avg_hits_per_entry\n")
        for mode, label in zip(modes, mode_labels):
            r = all_results.get(mode, {})
            eff = r.get("cache_efficiency", {})
            f.write(f"{label},{r.get('avg_latency_ms',0):.2f},{r.get('p50_latency_ms',0):.2f},{r.get('p95_latency_ms',0):.2f},{r.get('hit_rate',0):.4f},{r.get('llm_calls',0)},{r.get('cache_hits',0)},{r.get('cache_misses',0)},{r.get('cost_saved',0):.4f},{eff.get('total_entries',0)},{eff.get('avg_hits_per_entry',0):.2f}\n")
    print(f"CSV saved: {csv_path}")

    md_path = os.path.join(output_dir, "benchmark_report.md")
    from datetime import timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = f"""# Intelligent Cache Benchmark Report
Generated: {now}

## Summary Comparison

| Metric | No Cache | Exact Cache | Semantic Cache | Intelligent Multi-Level |
|--------|----------|-------------|----------------|-------------------------|
"""
    for metric in ["avg_latency_ms", "hit_rate", "llm_calls", "cache_hits", "cost_saved"]:
        row = f"| {metric} "
        for mode in modes:
            val = all_results.get(mode, {}).get(metric, 0)
            if metric == "hit_rate":
                row += f"| {val:.1%} "
            elif metric == "cost_saved":
                row += f"| ${val:.4f} "
            else:
                row += f"| {val:.1f} "
        row += "|\n"
        md += row

    md += "\n## Cache Efficiency\n\n"
    md += "| Mode | Total Entries | Avg Hits/Entry | Evictions |\n"
    md += "|------|---------------|----------------|----------|\n"
    for mode, label in zip(modes, mode_labels):
        r = all_results.get(mode, {})
        eff = r.get("cache_efficiency", {})
        md += f"| {label} | {eff.get('total_entries',0)} | {eff.get('avg_hits_per_entry',0):.2f} | {eff.get('evictions',0)} |\n"

    md += "\n## Detailed Results\n\n"
    for mode, label in zip(modes, mode_labels):
        r = all_results.get(mode, {})
        eff = r.get("cache_efficiency", {})
        md += f"""### {label}
- Total Queries: {r.get('total_queries', 0)}
- LLM Calls: {r.get('llm_calls', 0)}
- Cache Hits: {r.get('cache_hits', 0)}
- Cache Misses: {r.get('cache_misses', 0)}
- Hit Rate: {r.get('hit_rate', 0):.1%}
- Avg Latency: {r.get('avg_latency_ms', 0):.1f} ms
- P50 Latency: {r.get('p50_latency_ms', 0):.1f} ms
- P95 Latency: {r.get('p95_latency_ms', 0):.1f} ms
- Tokens Saved: {r.get('tokens_saved', 0):.0f}
- Cost Saved: ${r.get('cost_saved', 0):.4f}
- Cache Entries: {eff.get('total_entries', 0)}
- Avg Hits/Entry: {eff.get('avg_hits_per_entry', 0):.2f}
- Evictions: {eff.get('evictions', 0)}

"""
    md += """## Methodology

- **No Cache**: Every query goes directly to the LLM with no caching.
- **Exact Cache**: Uses Redis for exact string matching with SHA256 hashing.
- **Semantic Cache**: Uses PostgreSQL/pgvector for embedding-based similarity search.
- **Intelligent Multi-Level**: Combines exact and semantic caches with intelligent policy scoring.

## Environment

- Python 3.12
- Redis 7 (via Docker)
- PostgreSQL 16 with pgvector (via Docker)
- Mock LLM delay: {benchmark_delay_ms} ms (simulated)
""".format(benchmark_delay_ms=benchmark_delay_ms)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved: {md_path}")


def generate_graphs(all_results: Dict[str, Dict[str, Any]], output_dir: str):
    """Generate matplotlib graphs."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping graph generation")
        return

    os.makedirs(output_dir, exist_ok=True)
    modes = ["no_cache", "exact_cache", "semantic_cache", "intelligent_multi_level"]
    mode_labels = ["No Cache", "Exact", "Semantic", "Intelligent"]

    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]

    def get_metric(mode, metric):
        return all_results.get(mode, {}).get(metric, 0)

    def get_efficiency(mode):
        return all_results.get(mode, {}).get("cache_efficiency", {})

    # Graph 1: Average latency
    fig, ax = plt.subplots(figsize=(10, 6))
    values = [get_metric(m, "avg_latency_ms") for m in modes]
    bars = ax.bar(mode_labels, values, color=colors)
    ax.set_ylabel("Average Latency (ms)")
    ax.set_title("Average Latency Comparison")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{val:.1f}ms", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "latency_comparison.png"), dpi=150)
    plt.close()

    # Graph 2: P50 and P95 latency
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(mode_labels))
    width = 0.35
    p50 = [get_metric(m, "p50_latency_ms") for m in modes]
    p95 = [get_metric(m, "p95_latency_ms") for m in modes]
    ax.bar(x - width/2, p50, width, label="P50", color="#3498db")
    ax.bar(x + width/2, p95, width, label="P95", color="#e74c3c")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("P50 and P95 Latency Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(mode_labels)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "percentile_latency.png"), dpi=150)
    plt.close()

    # Graph 3: Cache hit rate
    fig, ax = plt.subplots(figsize=(10, 6))
    values = [get_metric(m, "hit_rate") * 100 for m in modes]
    bars = ax.bar(mode_labels, values, color=colors)
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Cache Hit Rate Comparison")
    ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 100)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{val:.1f}%", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "cache_hit_rate.png"), dpi=150)
    plt.close()

    # Graph 4: LLM calls vs avoided
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(mode_labels))
    width = 0.35
    calls = [get_metric(m, "llm_calls") for m in modes]
    avoided = [get_metric(m, "cache_hits") for m in modes]
    ax.bar(x - width/2, calls, width, label="LLM Calls", color="#e74c3c")
    ax.bar(x + width/2, avoided, width, label="Cache Hits / Avoided", color="#2ecc71")
    ax.set_ylabel("Count")
    ax.set_title("LLM Calls vs Cache Hits")
    ax.set_xticks(x)
    ax.set_xticklabels(mode_labels)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "llm_calls.png"), dpi=150)
    plt.close()

    # Graph 5: Threshold analysis (semantic + intelligent)
    if "threshold_results" in all_results:
        thr = all_results["threshold_results"]
        thresholds = thr.get("thresholds", [])
        semantic_hits = thr.get("semantic_hit_rates", [])
        intelligent_hits = thr.get("intelligent_hit_rates", [])
        semantic_lat = thr.get("semantic_avg_latencies", [])
        intelligent_lat = thr.get("intelligent_avg_latencies", [])

        if thresholds:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            ax1.plot(thresholds, [h*100 for h in semantic_hits], marker="o", label="Semantic", color="#3498db")
            ax1.plot(thresholds, [h*100 for h in intelligent_hits], marker="s", label="Intelligent", color="#9b59b6")
            ax1.set_xlabel("Semantic Threshold")
            ax1.set_ylabel("Hit Rate (%)")
            ax1.set_title("Threshold vs Cache Hit Rate")
            ax1.legend()
            ax1.grid(True)

            ax2.plot(thresholds, semantic_lat, marker="o", label="Semantic", color="#3498db")
            ax2.plot(thresholds, intelligent_lat, marker="s", label="Intelligent", color="#9b59b6")
            ax2.set_xlabel("Semantic Threshold")
            ax2.set_ylabel("Average Latency (ms)")
            ax2.set_title("Threshold vs Average Latency")
            ax2.legend()
            ax2.grid(True)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, "threshold_analysis.png"), dpi=150)
            plt.close()

    # Graph 6: Memory efficiency
    fig, ax = plt.subplots(figsize=(10, 6))
    semantic_eff = get_efficiency("semantic_cache")
    intelligent_eff = get_efficiency("intelligent_multi_level")
    values = [semantic_eff.get("total_entries", 0), intelligent_eff.get("total_entries", 0)]
    labels = ["Semantic", "Intelligent"]
    bars = ax.bar(labels, values, color=["#3498db", "#9b59b6"])
    ax.set_ylabel("Total Cache Entries")
    ax.set_title("Cache Entries: Semantic vs Intelligent")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, str(val), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "memory_efficiency.png"), dpi=150)
    plt.close()

    # Graph 7: Cost comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    values = [get_metric(m, "cost_saved") for m in modes]
    bars = ax.bar(mode_labels, values, color=colors)
    ax.set_ylabel("Estimated Cost Saved ($)")
    ax.set_title("Estimated Cost Savings Comparison")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.00001, f"${val:.4f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "cost_comparison.png"), dpi=150)
    plt.close()

    print(f"Graphs saved to: {output_dir}")


def main():
    print("=" * 60)
    print("Intelligent Cache Benchmark")
    print("=" * 60)

    num_queries = int(os.getenv("BENCHMARK_QUERIES", "200"))
    seed = int(os.getenv("BENCHMARK_SEED", "42"))
    runs = int(os.getenv("BENCHMARK_RUNS", "1"))
    benchmark_delay_ms = int(os.getenv("BENCHMARK_LLM_DELAY_MS", "1000"))
    output_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(output_dir, exist_ok=True)

    random.seed(seed)
    np.random.seed(seed)

    print(f"\nGenerating {num_queries} synthetic queries...")
    queries = generate_synthetic_queries(num_queries)
    print(f"Generated {len(queries)} queries")

    type_counts: dict[str, int] = {}
    for q in queries:
        t = q["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"Query types: {type_counts}")

    workload_path = os.path.join(output_dir, "workloads", "workload.csv")
    save_workload_csv(queries, workload_path)
    print(f"Workload saved: {workload_path}")

    print("\nInitializing components...")
    from app.llm.mock_provider import MockProvider
    llm = MockProvider(latency_ms=benchmark_delay_ms)
    cache_manager = CacheManager()
    metrics = MetricsCollector()
    encoder = EmbeddingEncoder()

    modes = ["no_cache", "exact_cache", "semantic_cache", "intelligent_multi_level"]
    all_results: Dict[str, Dict[str, Any]] = {}

    for mode in modes:
        run_results = []
        for run in range(runs):
            print(f"\nRunning benchmark: {mode} (run {run + 1}/{runs})...")
            _reset_state(cache_manager, metrics)
            if mode == "intelligent_multi_level":
                print("  Warming up intelligent cache...")
                _warmup_intelligent(cache_manager, metrics, encoder, llm, queries)
                metrics.clear()
            results = run_benchmark(mode, queries, llm, cache_manager, metrics, encoder)
            run_results.append(results)
            print_results(results)

        avg_results = _average_results(run_results)
        all_results[mode] = avg_results
        print(f"\nAverage results for {mode}:")
        print_results(avg_results)

    threshold_results = run_threshold_experiments(
        queries, llm, cache_manager, metrics, encoder
    )
    all_results["threshold_results"] = threshold_results

    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<25} {'No Cache':>12} {'Exact':>12} {'Semantic':>12} {'Intelligent':>12}")
    print("-" * 75)
    for metric in ["avg_latency_ms", "hit_rate", "llm_calls", "cache_hits", "cost_saved"]:
        row = f"{metric:<25}"
        for mode in modes:
            val = all_results.get(mode, {}).get(metric, 0)
            if metric == "hit_rate":
                row += f" {val:>11.1%}"
            elif metric == "cost_saved":
                row += f" ${val:>10.4f}"
            else:
                row += f" {val:>12.1f}"
        print(row)
    print("=" * 60)

    save_results(all_results, output_dir)
    generate_graphs(all_results, output_dir)


def _warmup_intelligent(
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
    llm,
    queries: List[Dict[str, Any]],
) -> None:
    """Pre-run workload to populate cache and establish frequencies for intelligent mode."""
    for query_data in queries:
        query_text = query_data["text"]
        embedding = encoder.encode(query_text)
        cache_result = cache_manager.get(query_text, context=embedding)
        if cache_result is None:
            response = llm.generate(query_text)
            cache_manager.set(query_text, response, context=embedding)
            metrics.record_cache_miss()
        else:
            metrics.record_cache_hit(cache_result.get("cache_type", "exact"))

def _reset_state(cache_manager: CacheManager, metrics: MetricsCollector) -> None:
    """Completely reset cache and metrics state between benchmark modes."""
    cache_manager.clear_all()
    metrics.clear()

    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.flushall()
    except Exception:
        pass

    try:
        from app.database.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE semantic_cache"))
            conn.execute(text("TRUNCATE TABLE context_cache"))
            conn.execute(text("TRUNCATE TABLE tool_cache"))
            conn.commit()
    except Exception:
        pass


def _reset_cache_only(cache_manager: CacheManager) -> None:
    """Clear caches and decisions but preserve query frequencies for intelligent warmup."""
    for cache in (cache_manager.exact, cache_manager.semantic, cache_manager.context, cache_manager.tool):
        try:
            cache.clear()
        except Exception:
            pass
    cache_manager._cache_decisions.clear()
    cache_manager._hits_per_entry.clear()


def _average_results(run_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not run_results:
        return {}
    avg = run_results[0].copy()
    numeric_fields = [
        "llm_calls", "cache_hits", "cache_misses", "total_latency_ms",
        "tokens_saved", "cost_saved", "avg_latency_ms", "p50_latency_ms",
        "p95_latency_ms", "min_latency_ms", "max_latency_ms", "hit_rate",
        "exact_hits", "semantic_hits", "tool_hits", "context_hits",
    ]
    for field in numeric_fields:
        values = [r.get(field, 0) for r in run_results]
        avg[field] = float(np.mean(values))
    all_latencies = []
    for r in run_results:
        all_latencies.extend(r.get("latencies", []))
    if all_latencies:
        avg["latencies"] = all_latencies
        avg["avg_latency_ms"] = float(np.mean(all_latencies))
        avg["p50_latency_ms"] = float(np.percentile(all_latencies, 50))
        avg["p95_latency_ms"] = float(np.percentile(all_latencies, 95))
        avg["min_latency_ms"] = float(np.min(all_latencies))
        avg["max_latency_ms"] = float(np.max(all_latencies))
    avg["runs"] = len(run_results)

    effs = [r.get("cache_efficiency", {}) for r in run_results]
    avg["cache_efficiency"] = {
        "total_entries": int(np.mean([e.get("total_entries", 0) for e in effs])),
        "unique_entries": int(np.mean([e.get("unique_entries", 0) for e in effs])),
        "evictions": int(np.mean([e.get("evictions", 0) for e in effs])),
        "expired_entries": int(np.mean([e.get("expired_entries", 0) for e in effs])),
        "avg_hits_per_entry": float(np.mean([e.get("avg_hits_per_entry", 0.0) for e in effs])),
    }
    return avg





def run_threshold_experiments(
    queries: List[Dict[str, Any]],
    llm,
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
) -> Dict[str, Any]:
    """Run semantic threshold experiments."""
    thresholds = [0.75, 0.80, 0.85, 0.90, 0.95]
    subset_size = min(200, len(queries))
    subset = queries[:subset_size]
    results: Dict[str, Any] = {
        "thresholds": thresholds,
        "semantic_hit_rates": [],
        "intelligent_hit_rates": [],
        "semantic_avg_latencies": [],
        "intelligent_avg_latencies": [],
        "semantic_llm_calls": [],
        "intelligent_llm_calls": [],
    }

    for thr in thresholds:
        cache_manager.clear_all()
        metrics.clear()

        sem = run_benchmark(
            "semantic_cache", subset, llm, cache_manager, metrics, encoder, semantic_threshold=thr
        )
        cache_manager.clear_all()
        metrics.clear()

        intel = run_benchmark(
            "intelligent_multi_level", subset, llm, cache_manager, metrics, encoder, semantic_threshold=thr
        )

        results["semantic_hit_rates"].append(sem.get("hit_rate", 0.0))
        results["intelligent_hit_rates"].append(intel.get("hit_rate", 0.0))
        results["semantic_avg_latencies"].append(sem.get("avg_latency_ms", 0.0))
        results["intelligent_avg_latencies"].append(intel.get("avg_latency_ms", 0.0))
        results["semantic_llm_calls"].append(sem.get("llm_calls", 0))
        results["intelligent_llm_calls"].append(intel.get("llm_calls", 0))

        print(f"Threshold {thr:.2f}: Semantic hit={sem.get('hit_rate',0):.1%}, Intelligent hit={intel.get('hit_rate',0):.1%}")

    return results


def run_capacity_experiments(
    queries: List[Dict[str, Any]],
    llm,
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
) -> Dict[str, Any]:
    """Run cache capacity experiments."""
    capacities = [10, 25, 50, 100, 250]
    results: Dict[str, Any] = {
        "capacities": capacities,
        "semantic_hit_rates": [],
        "intelligent_hit_rates": [],
        "semantic_entries": [],
        "intelligent_entries": [],
        "semantic_avg_hits": [],
        "intelligent_avg_hits": [],
    }

    for cap in capacities:
        cache_manager.clear_all()
        metrics.clear()
        cache_manager.exact.max_entries = cap
        cache_manager.semantic.max_entries = cap

        sem = run_benchmark("semantic_cache", queries, llm, cache_manager, metrics, encoder)
        cache_manager.clear_all()
        metrics.clear()

        intel = run_benchmark("intelligent_multi_level", queries, llm, cache_manager, metrics, encoder)

        results["semantic_hit_rates"].append(sem.get("hit_rate", 0.0))
        results["intelligent_hit_rates"].append(intel.get("hit_rate", 0.0))
        results["semantic_entries"].append(sem.get("cache_efficiency", {}).get("total_entries", 0))
        results["intelligent_entries"].append(intel.get("cache_efficiency", {}).get("total_entries", 0))
        results["semantic_avg_hits"].append(sem.get("cache_efficiency", {}).get("avg_hits_per_entry", 0.0))
        results["intelligent_avg_hits"].append(intel.get("cache_efficiency", {}).get("avg_hits_per_entry", 0.0))

        print(f"Capacity {cap}: Semantic hit={sem.get('hit_rate',0):.1%}, Intelligent hit={intel.get('hit_rate',0):.1%}")

    return results


def run_ttl_experiments(
    queries: List[Dict[str, Any]],
    llm,
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
) -> Dict[str, Any]:
    """Run TTL experiments."""
    ttls = [10, 30, 60, 300]
    results: Dict[str, Any] = {
        "ttls": ttls,
        "semantic_hit_rates": [],
        "intelligent_hit_rates": [],
        "semantic_entries": [],
        "intelligent_entries": [],
    }

    for ttl in ttls:
        cache_manager.clear_all()
        metrics.clear()
        cache_manager.exact.default_ttl = ttl
        cache_manager.semantic.default_ttl = ttl

        sem = run_benchmark("semantic_cache", queries, llm, cache_manager, metrics, encoder)
        cache_manager.clear_all()
        metrics.clear()

        intel = run_benchmark("intelligent_multi_level", queries, llm, cache_manager, metrics, encoder)

        results["semantic_hit_rates"].append(sem.get("hit_rate", 0.0))
        results["intelligent_hit_rates"].append(intel.get("hit_rate", 0.0))
        results["semantic_entries"].append(sem.get("cache_efficiency", {}).get("total_entries", 0))
        results["intelligent_entries"].append(intel.get("cache_efficiency", {}).get("total_entries", 0))

        print(f"TTL {ttl}s: Semantic hit={sem.get('hit_rate',0):.1%}, Intelligent hit={intel.get('hit_rate',0):.1%}")

    return results


def main():
    print("=" * 60)
    print("Intelligent Cache Benchmark")
    print("=" * 60)

    num_queries = int(os.getenv("BENCHMARK_QUERIES", "200"))
    seed = int(os.getenv("BENCHMARK_SEED", "42"))
    runs = int(os.getenv("BENCHMARK_RUNS", "1"))
    benchmark_delay_ms = int(os.getenv("BENCHMARK_LLM_DELAY_MS", "1000"))
    output_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(output_dir, exist_ok=True)

    random.seed(seed)
    np.random.seed(seed)

    print(f"\nGenerating {num_queries} synthetic queries...")
    queries = generate_synthetic_queries(num_queries)
    print(f"Generated {len(queries)} queries")

    type_counts: dict[str, int] = {}
    for q in queries:
        t = q["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"Query types: {type_counts}")

    workload_path = os.path.join(output_dir, "workloads", "workload.csv")
    save_workload_csv(queries, workload_path)
    print(f"Workload saved: {workload_path}")

    print("\nInitializing components...")
    from app.llm.mock_provider import MockProvider
    llm = MockProvider(latency_ms=benchmark_delay_ms)
    cache_manager = CacheManager()
    metrics = MetricsCollector()
    encoder = EmbeddingEncoder()

    modes = ["no_cache", "exact_cache", "semantic_cache", "intelligent_multi_level"]
    all_results: Dict[str, Dict[str, Any]] = {}

    for mode in modes:
        run_results = []
        for run in range(runs):
            print(f"\nRunning benchmark: {mode} (run {run + 1}/{runs})...")
            _reset_state(cache_manager, metrics)
            if mode == "intelligent_multi_level":
                print("  Warming up intelligent cache...")
                _warmup_intelligent(cache_manager, metrics, encoder, llm, queries)
                metrics.clear()
            results = run_benchmark(mode, queries, llm, cache_manager, metrics, encoder)
            run_results.append(results)
            print_results(results)

        avg_results = _average_results(run_results)
        all_results[mode] = avg_results
        print(f"\nAverage results for {mode}:")
        print_results(avg_results)

    threshold_results = run_threshold_experiments(
        queries, llm, cache_manager, metrics, encoder
    )
    all_results["threshold_results"] = threshold_results

    capacity_results = run_capacity_experiments(
        queries, llm, cache_manager, metrics, encoder
    )
    all_results["capacity_results"] = capacity_results

    ttl_results = run_ttl_experiments(
        queries, llm, cache_manager, metrics, encoder
    )
    all_results["ttl_results"] = ttl_results

    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<25} {'No Cache':>12} {'Exact':>12} {'Semantic':>12} {'Intelligent':>12}")
    print("-" * 75)
    for metric in ["avg_latency_ms", "hit_rate", "llm_calls", "cache_hits", "cost_saved"]:
        row = f"{metric:<25}"
        for mode in modes:
            val = all_results.get(mode, {}).get(metric, 0)
            if metric == "hit_rate":
                row += f" {val:>11.1%}"
            elif metric == "cost_saved":
                row += f" ${val:>10.4f}"
            else:
                row += f" {val:>12.1f}"
        print(row)
    print("=" * 60)

    save_results(all_results, output_dir)
    generate_graphs(all_results, output_dir)


def _warmup_intelligent(
    cache_manager: CacheManager,
    metrics: MetricsCollector,
    encoder: EmbeddingEncoder,
    llm,
    queries: List[Dict[str, Any]],
) -> None:
    """Pre-run workload to populate cache and establish frequencies for intelligent mode."""
    for query_data in queries:
        query_text = query_data["text"]
        embedding = encoder.encode(query_text)
        cache_result = cache_manager.get(query_text, context=embedding)
        if cache_result is None:
            response = llm.generate(query_text)
            cache_manager.set(query_text, response, context=embedding)
            metrics.record_cache_miss()
        else:
            metrics.record_cache_hit(cache_result.get("cache_type", "exact"))


def _reset_state(cache_manager: CacheManager, metrics: MetricsCollector) -> None:
    """Completely reset cache and metrics state between benchmark modes."""
    cache_manager.clear_all()
    metrics.clear()

    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.flushall()
    except Exception:
        pass

    try:
        from app.database.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE semantic_cache"))
            conn.execute(text("TRUNCATE TABLE context_cache"))
            conn.execute(text("TRUNCATE TABLE tool_cache"))
            conn.commit()
    except Exception:
        pass


def _reset_cache_only(cache_manager: CacheManager) -> None:
    """Clear caches and decisions but preserve query frequencies for intelligent warmup."""
    for cache in (cache_manager.exact, cache_manager.semantic, cache_manager.context, cache_manager.tool):
        try:
            cache.clear()
        except Exception:
            pass
    cache_manager._cache_decisions.clear()
    cache_manager._hits_per_entry.clear()


def _average_results(run_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not run_results:
        return {}
    avg = run_results[0].copy()
    numeric_fields = [
        "llm_calls", "cache_hits", "cache_misses", "total_latency_ms",
        "tokens_saved", "cost_saved", "avg_latency_ms", "p50_latency_ms",
        "p95_latency_ms", "min_latency_ms", "max_latency_ms", "hit_rate",
        "exact_hits", "semantic_hits", "tool_hits", "context_hits",
    ]
    for field in numeric_fields:
        values = [r.get(field, 0) for r in run_results]
        avg[field] = float(np.mean(values))
    all_latencies = []
    for r in run_results:
        all_latencies.extend(r.get("latencies", []))
    if all_latencies:
        avg["latencies"] = all_latencies
        avg["avg_latency_ms"] = float(np.mean(all_latencies))
        avg["p50_latency_ms"] = float(np.percentile(all_latencies, 50))
        avg["p95_latency_ms"] = float(np.percentile(all_latencies, 95))
        avg["min_latency_ms"] = float(np.min(all_latencies))
        avg["max_latency_ms"] = float(np.max(all_latencies))
    avg["runs"] = len(run_results)

    effs = [r.get("cache_efficiency", {}) for r in run_results]
    avg["cache_efficiency"] = {
        "total_entries": int(np.mean([e.get("total_entries", 0) for e in effs])),
        "unique_entries": int(np.mean([e.get("unique_entries", 0) for e in effs])),
        "evictions": int(np.mean([e.get("evictions", 0) for e in effs])),
        "expired_entries": int(np.mean([e.get("expired_entries", 0) for e in effs])),
        "avg_hits_per_entry": float(np.mean([e.get("avg_hits_per_entry", 0.0) for e in effs])),
    }
    return avg

if __name__ == "__main__":
    main()
