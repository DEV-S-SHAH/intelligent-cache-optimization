"""Streamlit monitoring dashboard for cache performance."""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.metrics.collector import MetricsCollector
from app.cache.manager import CacheManager
from app.database.session import get_db
from app.database.models import SemanticCacheEntry, ContextCacheEntry, ToolCacheEntry

st.set_page_config(page_title="Intelligent Cache Dashboard", layout="wide")

st.title("🧠 Intelligent Caching Optimization Middleware")
st.markdown("Real-time monitoring dashboard for AI agent caching performance")


def init_components():
    if "metrics" not in st.session_state:
        st.session_state.metrics = MetricsCollector()
    if "cache_manager" not in st.session_state:
        st.session_state.cache_manager = CacheManager()


init_components()
metrics: MetricsCollector = st.session_state.metrics
cache_manager: CacheManager = st.session_state.cache_manager

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    st.info("API Base URL: http://localhost:8000")
    st.markdown("---")
    st.markdown("### Actions")
    if st.button("Clear All Caches"):
        cache_manager.clear_all()
        metrics.clear()
        st.success("Caches cleared!")
    if st.button("Refresh Metrics"):
        st.rerun()

# Query Demo Section
st.header("🔍 Query Demo")
col1, col2 = st.columns([2, 1])

with col1:
    query = st.text_input("Enter a query:", placeholder="What is the capital of France?")
    session_id = st.text_input("Session ID (optional):", value="demo-session-1")
    use_cache = st.checkbox("Use Cache", value=True)

    if st.button("Send Query", type="primary") and query:
        with st.spinner("Processing..."):
            import httpx

            try:
                start_time = time.time()
                response = httpx.post(
                    "http://localhost:8000/generate",
                    json={
                        "prompt": query,
                        "session_id": session_id if session_id else None,
                        "use_cache": use_cache
                    },
                    timeout=30.0
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    result = response.json()
                    st.json(result)
                    st.metric("Actual Latency", f"{result.get('latency_ms', 0):.1f} ms")
                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"Connection Error: {e}")
                st.warning("Make sure the API server is running on http://localhost:8000")

with col2:
    st.markdown("### How to Demo")
    st.markdown("""
    1. Enter Query 1 → Cache MISS → LLM → Store
    2. Enter similar Query → Semantic HIT → No LLM → Fast Response
    3. Check metrics below for hit rate
    """)

st.markdown("---")

# Metrics Section
stats = metrics.get_stats()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Requests", stats.get("total_requests", 0))
with col2:
    st.metric("Cache Hit Rate", f"{stats.get('hit_rate', 0):.1%}")
with col3:
    st.metric("LLM Calls", stats.get("total_llm_calls", 0))
with col4:
    st.metric("LLM Calls Avoided", stats.get("total_llm_avoided", 0))

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Avg Latency", f"{stats.get('avg_latency_ms', 0):.1f} ms")
with col2:
    st.metric("P50 Latency", f"{stats.get('p50_latency_ms', 0):.1f} ms")
with col3:
    st.metric("P95 Latency", f"{stats.get('p95_latency_ms', 0):.1f} ms")
with col4:
    st.metric("Tokens Saved", stats.get("tokens_saved", 0))

col1, col2 = st.columns(2)
with col1:
    st.metric("Estimated Cost Saved", f"${stats.get('cost_saved', 0):.4f}")
with col2:
    st.metric("Evictions", stats.get("evictions", 0))

# Cache Efficiency Section
st.markdown("---")
st.header("📈 Cache Efficiency")

cache_stats = cache_manager.stats()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Cache Entries", cache_stats.get("total_entries", 0))
with col2:
    st.metric("Avg Hits per Entry", f"{cache_stats.get('avg_hits_per_entry', 0):.2f}")
with col3:
    st.metric("Evictions", cache_stats.get("evictions", 0))
with col4:
    st.metric("Expired Entries", cache_stats.get("expired_entries", 0))

# Cache Decision Distribution
decisions = cache_stats.get("cache_decision_distribution", {})
if decisions:
    st.subheader("Cache Decision Distribution")
    fig_decisions = px.pie(
        values=list(decisions.values()),
        names=list(decisions.keys()),
        title="Cache Policy Decisions",
        hole=0.4
    )
    st.plotly_chart(fig_decisions, use_container_width=True)

# Intelligent Policy Explanation
st.markdown("---")
st.header("🧠 Intelligent Policy Explanation")

if cache_manager._cache_decisions:
    recent_decisions = cache_manager._cache_decisions[-10:]
    decision_data = []
    for d in recent_decisions:
        decision_data.append({
            "Decision": d.get("decision", "unknown"),
            "Score": d.get("score", 0),
            "Reasons": ", ".join(d.get("reasons", [])),
            "Frequency": d.get("factors", {}).get("frequency_score", 0),
            "Similarity": d.get("factors", {}).get("similarity_score", 0),
            "Recency": d.get("factors", {}).get("recency_score", 0),
            "Reuse": d.get("factors", {}).get("reuse_probability", 0),
            "Cost": d.get("factors", {}).get("estimated_cost", 0),
            "Memory": d.get("factors", {}).get("memory_penalty", 0),
        })
    st.dataframe(pd.DataFrame(decision_data), use_container_width=True)
else:
    st.info("No policy decisions recorded yet. Send some queries to see the intelligent policy in action.")

# Charts Section
st.markdown("---")
st.header("📊 Analytics")

# Cache type distribution
type_dist = stats.get("cache_type_distribution", {})
if type_dist:
    fig_pie = px.pie(
        values=list(type_dist.values()),
        names=list(type_dist.keys()),
        title="Cache Hit Distribution by Type",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# Latency comparison
latency_data = {
    "Metric": ["Average", "P50", "P95"],
    "Latency (ms)": [
        stats.get("avg_latency_ms", 0),
        stats.get("p50_latency_ms", 0),
        stats.get("p95_latency_ms", 0)
    ]
}
if latency_data["Latency (ms)"][0] > 0:
    fig_latency = px.bar(
        latency_data,
        x="Metric",
        y="Latency (ms)",
        title="Latency Metrics",
        color="Metric"
    )
    st.plotly_chart(fig_latency, use_container_width=True)

# Before vs After comparison
st.subheader("Before vs After Cache")
col1, col2 = st.columns(2)
with col1:
    st.metric("Avg LLM Latency (Est.)", "1000 ms", delta="baseline")
with col2:
    avg_latency = stats.get("avg_latency_ms", 0)
    st.metric("Avg System Latency", f"{avg_latency:.1f} ms", delta=f"{-1000 + avg_latency:.1f} ms")

# Cached Entries
st.markdown("---")
st.header("📦 Cached Entries")

tab1, tab2, tab3 = st.tabs(["Semantic Cache", "Context Cache", "Tool Cache"])

with tab1:
    try:
        db = next(get_db())
        entries = db.query(SemanticCacheEntry).limit(20).all()
        if entries:
            data = []
            for e in entries:
                data.append({
                    "Query": e.query_text[:50] + "..." if len(e.query_text) > 50 else e.query_text,
                    "Hits": e.hit_count,
                    "Created": e.created_at.strftime("%Y-%m-%d %H:%M"),
                    "TTL": f"{e.ttl_seconds}s" if e.ttl_seconds else "None"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("No semantic cache entries yet")
        db.close()
    except Exception as e:
        st.error(f"Error loading entries: {e}")

with tab2:
    try:
        db = next(get_db())
        entries = db.query(ContextCacheEntry).limit(20).all()
        if entries:
            data = []
            for e in entries:
                data.append({
                    "Session ID": e.session_id,
                    "Created": e.created_at.strftime("%Y-%m-%d %H:%M"),
                    "TTL": f"{e.ttl_seconds}s" if e.ttl_seconds else "None"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("No context cache entries yet")
        db.close()
    except Exception as e:
        st.error(f"Error loading entries: {e}")

with tab3:
    try:
        db = next(get_db())
        entries = db.query(ToolCacheEntry).limit(20).all()
        if entries:
            data = []
            for e in entries:
                data.append({
                    "Tool": e.tool_name,
                    "Args Hash": e.args_hash[:16] + "...",
                    "Created": e.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Deterministic": e.is_deterministic
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("No tool cache entries yet")
        db.close()
    except Exception as e:
        st.error(f"Error loading entries: {e}")

# Benchmark Results Section
st.markdown("---")
st.header("📊 Benchmark Results")

try:
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    json_path = os.path.join(results_dir, "benchmark_results.json")
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            benchmark_data = json.load(f)

        modes = ["no_cache", "exact_cache", "semantic_cache", "intelligent_multi_level"]
        mode_labels = ["No Cache", "Exact", "Semantic", "Intelligent"]

        st.subheader("Performance Comparison")
        comparison_data = []
        for mode, label in zip(modes, mode_labels):
            r = benchmark_data.get(mode, {})
            comparison_data.append({
                "Mode": label,
                "Avg Latency (ms)": r.get("avg_latency_ms", 0),
                "P50 Latency (ms)": r.get("p50_latency_ms", 0),
                "P95 Latency (ms)": r.get("p95_latency_ms", 0),
                "Hit Rate": f"{r.get('hit_rate', 0):.1%}",
                "LLM Calls": r.get("llm_calls", 0),
                "Cache Hits": r.get("cache_hits", 0),
                "Cost Saved ($)": f"{r.get('cost_saved', 0):.4f}",
            })
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True)

        if "threshold_results" in benchmark_data:
            st.subheader("Threshold Analysis")
            thr = benchmark_data["threshold_results"]
            threshold_data = []
            thresholds = thr.get("thresholds", [])
            semantic_hits = thr.get("semantic_hit_rates", [])
            intelligent_hits = thr.get("intelligent_hit_rates", [])
            for i, t in enumerate(thresholds):
                threshold_data.append({
                    "Threshold": t,
                    "Semantic Hit Rate": f"{semantic_hits[i]:.1%}" if i < len(semantic_hits) else "N/A",
                    "Intelligent Hit Rate": f"{intelligent_hits[i]:.1%}" if i < len(intelligent_hits) else "N/A",
                })
            st.dataframe(pd.DataFrame(threshold_data), use_container_width=True)
    else:
        st.info("Run `python scripts/benchmark.py` to generate benchmark results.")
except Exception as e:
    st.error(f"Error loading benchmark results: {e}")

# Footer
st.markdown("---")
st.caption("Intelligent Caching Optimization Middleware for AI Agents | M.Tech Project")
