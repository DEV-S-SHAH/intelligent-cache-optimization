import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Intelligent Cache Dashboard", layout="wide")
st.title("Intelligent Caching Optimization Middleware for AI Agents")

API_URL = st.sidebar.text_input("API URL", value="http://localhost:8000/api/v1")

st.sidebar.header("Actions")
if st.sidebar.button("Clear Cache"):
    try:
        r = requests.delete(f"{API_URL}/cache")
        st.sidebar.success("Cache cleared")
    except Exception as e:
        st.sidebar.error(f"Failed: {e}")

tab1, tab2, tab3 = st.tabs(["Metrics", "Cache Entries", "Demo"])

with tab1:
    st.header("Real-time Metrics")
    if st.button("Refresh Metrics"):
        pass

    try:
        r = requests.get(f"{API_URL}/metrics")
        if r.status_code == 200:
            data = r.json()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Requests", data["total_requests"])
            col2.metric("Cache Hit Rate", f"{data['cache_hit_rate']:.1%}")
            col3.metric("LLM Calls", data["llm_calls"])
            col4.metric("LLM Calls Avoided", data["llm_calls_avoided"])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Avg Latency", f"{data['avg_latency_ms']:.1f} ms")
            col2.metric("P50 Latency", f"{data['p50_latency_ms']:.1f} ms")
            col3.metric("P95 Latency", f"{data['p95_latency_ms']:.1f} ms")
            col4.metric("Cost Saved", f"${data['estimated_cost_saved']:.4f}")

            st.subheader("Cache Type Distribution")
            hit_data = {
                "Exact": data["exact_hits"],
                "Semantic": data["semantic_hits"],
                "Context": data["context_hits"],
                "Tool": data["tool_hits"],
            }
            df_hits = pd.DataFrame(list(hit_data.items()), columns=["Cache Type", "Hits"])
            fig = px.pie(df_hits, values="Hits", names="Cache Type", title="Hits by Cache Type")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Latency Distribution")
            latencies = [data["avg_latency_ms"], data["p50_latency_ms"], data["p95_latency_ms"]]
            df_lat = pd.DataFrame({"Metric": ["Avg", "P50", "P95"], "Latency (ms)": latencies})
            fig2 = px.bar(df_lat, x="Metric", y="Latency (ms)", title="Latency Metrics")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.error(f"Failed to fetch metrics: {r.status_code}")
    except Exception as e:
        st.error(f"Connection error: {e}")

with tab2:
    st.header("Cache Statistics")
    try:
        r = requests.get(f"{API_URL}/cache/stats")
        if r.status_code == 200:
            stats = r.json()
            for cache_type, info in stats.items():
                with st.expander(f"{cache_type.upper()} Cache"):
                    st.json(info)
        else:
            st.error(f"Failed to fetch stats: {r.status_code}")
    except Exception as e:
        st.error(f"Connection error: {e}")

with tab3:
    st.header("Interactive Demo")
    st.subheader("Query the Cache Layer")
    query = st.text_input("Enter your query:", placeholder="e.g., What is Python?")
    session_id = st.text_input("Session ID (optional):", value="demo-session-1")
    use_tools = st.checkbox("Use deterministic tools")
    cache_type = st.selectbox("Preferred cache type", ["", "exact", "semantic"], index=0)

    if st.button("Send Query"):
        if not query.strip():
            st.warning("Please enter a query")
        else:
            payload = {
                "query": query,
                "session_id": session_id or None,
                "use_tools": use_tools,
                "cache_type": cache_type or None,
            }
            try:
                start = time.perf_counter()
                r = requests.post(f"{API_URL}/generate", json=payload)
                latency = (time.perf_counter() - start) * 1000
                if r.status_code == 200:
                    data = r.json()
                    st.subheader("Response")
                    if data.get("tool_used"):
                        st.info(f"Tool used: {data['tool_used']}")
                    st.write(data["response"])
                    st.subheader("Cache Information")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Status", data["cache_status"])
                    col2.metric("Cache Type", data.get("cache_type", "N/A"))
                    col3.metric("Latency", f"{data['latency_ms']:.1f} ms")
                    if data.get("similarity_score"):
                        st.metric("Similarity Score", f"{data['similarity_score']:.2f}")
                    if data.get("tokens_used"):
                        st.metric("Tokens Used", data["tokens_used"])
                    st.caption(f"Total roundtrip: {latency:.1f} ms")
                else:
                    st.error(f"Request failed: {r.status_code} - {r.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    st.subheader("Try Similar Queries")
    st.caption("Send Query 1 first (MISS), then a paraphrased version to see Semantic HIT")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("What is caching in AI?"):
            st.session_state["demo_query"] = "What is caching in AI?"
    with col2:
        if st.button("Explain caching mechanisms for artificial intelligence"):
            st.session_state["demo_query"] = "Explain caching mechanisms for artificial intelligence"

    if "demo_query" in st.session_state:
        st.text_input("Query:", value=st.session_state["demo_query"], key="demo_query_display")
