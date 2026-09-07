"""Workload generator for cache benchmarking."""

import os
import random
import string
from typing import List, Dict, Any

random.seed(int(os.getenv("BENCHMARK_SEED", "42")))


# Realistic query domains and templates
DOMAINS = {
    "ai_ml": [
        "What is machine learning?",
        "Explain neural networks",
        "What is deep learning?",
        "How does backpropagation work?",
        "What is reinforcement learning?",
        "Explain gradient descent",
        "What is a transformer architecture?",
        "How does attention mechanism work?",
        "What is overfitting?",
        "Explain batch normalization",
        "What is computer vision?",
        "How does convolutional neural network work?",
        "What is natural language processing?",
        "Explain recurrent neural networks",
        "What is transfer learning?",
    ],
    "databases": [
        "What is a relational database?",
        "Explain SQL joins",
        "What is database normalization?",
        "How does indexing work?",
        "What is ACID compliance?",
        "Explain transaction isolation levels",
        "What is a primary key?",
        "How does database sharding work?",
        "What is NoSQL?",
        "Explain CAP theorem",
        "What is database replication?",
        "How does query optimization work?",
    ],
    "networking": [
        "What is TCP/IP?",
        "Explain DNS resolution",
        "What is HTTP?",
        "How does SSL/TLS work?",
        "What is a firewall?",
        "Explain OSI model",
        "What is VPN?",
        "How does routing work?",
        "What is CDN?",
        "Explain load balancing",
        "What is latency?",
        "How does packet switching work?",
    ],
    "operating_systems": [
        "What is an operating system?",
        "Explain process scheduling",
        "What is virtual memory?",
        "How does file system work?",
        "What is a system call?",
        "Explain deadlock",
        "What is multithreading?",
        "How does memory management work?",
        "What is a kernel?",
        "Explain interrupt handling",
    ],
    "programming": [
        "What is object-oriented programming?",
        "Explain recursion",
        "What is a data structure?",
        "How does garbage collection work?",
        "What is functional programming?",
        "Explain Big O notation",
        "What is an API?",
        "How does a compiler work?",
        "What is debugging?",
        "Explain version control",
    ],
    "cloud_computing": [
        "What is cloud computing?",
        "Explain IaaS vs PaaS vs SaaS",
        "What is AWS?",
        "How does containerization work?",
        "What is Kubernetes?",
        "Explain serverless computing",
        "What is microservices architecture?",
        "How does auto-scaling work?",
        "What is cloud storage?",
        "Explain load balancer in cloud",
    ],
    "general_knowledge": [
        "What is the capital of France?",
        "Explain photosynthesis",
        "What is the speed of light?",
        "How does the water cycle work?",
        "What is gravity?",
        "Explain DNA structure",
        "What is climate change?",
        "How do vaccines work?",
        "What is the Pythagorean theorem?",
        "Explain the theory of relativity",
    ],
}

# Paraphrase templates
PARAPHRASE_TEMPLATES = [
    "What is {}?",
    "Can you explain {}?",
    "Tell me about {}",
    "How does {} work?",
    "What do you know about {}?",
    "I need information on {}",
    "Please describe {}",
    "Explain {} in simple terms",
    "Give me a summary of {}",
    "What can you tell me about {}?",
]

# Low-value / casual queries
LOW_VALUE_QUERIES = [
    "hi", "hello", "hey", "whats up", "ok", "thanks",
    "bye", "good morning", "good night", "yes", "no",
    "maybe", "i see", "got it", "cool", "nice",
]

# Query complexity tiers
COMPLEXITY_TIERS = {
    "simple": {
        "delay_ms": 300,
        "queries": [
            "hi", "hello", "ok", "thanks", "bye",
            "What is 2+2?", "What is the capital of France?",
        ]
    },
    "normal": {
        "delay_ms": 700,
        "queries": [
            "Explain how TCP/IP works",
            "What is machine learning?",
            "How does a database index work?",
        ]
    },
    "complex": {
        "delay_ms": 1200,
        "queries": [
            "Explain the transformer architecture in detail",
            "How does distributed consensus work in Kubernetes?",
            "What are the trade-offs of different database isolation levels?",
        ]
    },
    "long_context": {
        "delay_ms": 2000,
        "queries": [
            "Compare and contrast AWS Lambda with Azure Functions for serverless workloads",
            "Explain the complete lifecycle of an HTTP request from browser to server",
        ]
    },
}


def generate_workload(
    num_queries: int = 1000,
    distribution: Dict[str, float] = None,
) -> List[Dict[str, Any]]:
    """Generate a realistic mixed workload for benchmarking.

    Args:
        num_queries: Total number of queries to generate.
        distribution: Query type distribution. Default is:
            - exact_repeat: 20%
            - strong_semantic: 25%
            - weak_semantic: 10%
            - hot: 15%
            - unique: 15%
            - cold: 10%
            - dynamic_stale: 5%

    Returns:
        List of query dictionaries with text, type, base, complexity, and id.
    """
    if distribution is None:
        distribution = {
            "exact_repeat": 0.20,
            "strong_semantic": 0.25,
            "weak_semantic": 0.10,
            "hot": 0.15,
            "unique": 0.15,
            "cold": 0.10,
            "dynamic_stale": 0.05,
        }

    # Normalize distribution
    total_weight = sum(distribution.values())
    distribution = {k: v / total_weight for k, v in distribution.items()}

    queries = []
    query_id = 0

    # Calculate counts per type
    counts = {}
    remaining = num_queries
    for qtype, weight in distribution.items():
        if qtype == list(distribution.keys())[-1]:
            counts[qtype] = remaining
        else:
            counts[qtype] = int(num_queries * weight)
            remaining -= counts[qtype]

    # Collect all base queries from all domains
    all_queries = []
    for domain_queries in DOMAINS.values():
        all_queries.extend(domain_queries)

    # Select hot query bases (a small number repeated many times)
    hot_bases = random.sample(all_queries, k=min(5, len(all_queries)))

    # 1. Exact repeats - create actual repeated queries
    exact_count = counts.get("exact_repeat", 0)
    num_exact_bases = max(1, min(exact_count // 2, len(all_queries)))
    exact_bases = random.sample(all_queries, k=num_exact_bases)
    repeats_per_base = max(2, exact_count // len(exact_bases))
    for base in exact_bases:
        for _ in range(repeats_per_base):
            queries.append({
                "text": base,
                "type": "exact_repeat",
                "base": base,
                "complexity": _assign_complexity(base),
                "id": query_id,
            })
            query_id += 1
    # Trim to exact count if overshot
    while len([q for q in queries if q["type"] == "exact_repeat"]) > exact_count:
        # Remove last exact_repeat
        for i in range(len(queries) - 1, -1, -1):
            if queries[i]["type"] == "exact_repeat":
                queries.pop(i)
                break

    # 2. Strong semantic duplicates (paraphrases)
    for _ in range(counts.get("strong_semantic", 0)):
        base = random.choice(all_queries)
        template = random.choice(PARAPHRASE_TEMPLATES)
        topic = _extract_topic(base)
        paraphrase = template.replace("{}", topic)
        queries.append({
            "text": paraphrase,
            "type": "strong_semantic",
            "base": base,
            "complexity": _assign_complexity(base),
            "id": query_id,
        })
        query_id += 1

    # 3. Weak semantic queries (related but different)
    for _ in range(counts.get("weak_semantic", 0)):
        base = random.choice(all_queries)
        related = _get_related_query(base)
        queries.append({
            "text": related,
            "type": "weak_semantic",
            "base": base,
            "complexity": _assign_complexity(related),
            "id": query_id,
        })
        query_id += 1

    # 4. Hot queries (repeated many times)
    hot_repeats = max(1, counts.get("hot", 0) // len(hot_bases))
    for _ in range(counts.get("hot", 0)):
        base = random.choice(hot_bases)
        queries.append({
            "text": base,
            "type": "hot",
            "base": base,
            "complexity": _assign_complexity(base),
            "id": query_id,
        })
        query_id += 1

    # 5. Unique queries (should not be cached)
    for _ in range(counts.get("unique", 0)):
        base = random.choice(all_queries)
        suffix = "".join(random.choices(string.ascii_lowercase, k=random.randint(8, 20)))
        unique_q = f"{base} - {suffix}"
        queries.append({
            "text": unique_q,
            "type": "unique",
            "base": base,
            "complexity": _assign_complexity(base),
            "id": query_id,
        })
        query_id += 1

    # 6. Cold queries (rare, low value)
    for _ in range(counts.get("cold", 0)):
        q = random.choice(LOW_VALUE_QUERIES)
        queries.append({
            "text": q,
            "type": "cold",
            "base": q,
            "complexity": "simple",
            "id": query_id,
        })
        query_id += 1

    # 7. Dynamic/stale queries (should have short TTL)
    for _ in range(counts.get("dynamic_stale", 0)):
        base = random.choice(all_queries)
        time_suffix = f" (as of {random.randint(2020, 2024)})"
        dynamic_q = base + time_suffix
        queries.append({
            "text": dynamic_q,
            "type": "dynamic_stale",
            "base": base,
            "complexity": _assign_complexity(base),
            "id": query_id,
        })
        query_id += 1

    # Shuffle to simulate realistic interleaving
    random.shuffle(queries)
    return queries[:num_queries]


def _extract_topic(query: str) -> str:
    """Extract topic from a query for paraphrasing."""
    topic = query.lower()
    topic = topic.replace("what is", "").replace("explain", "").replace("how does", "")
    topic = topic.replace("how do", "").replace("?", "").strip()
    return topic if topic else query


def _get_related_query(base: str) -> str:
    """Get a related but different query for weak semantic similarity."""
    templates = [
        f"Difference between {base.lower()} and alternatives",
        f"Best practices for {base.lower()}",
        f"Common issues with {base.lower()}",
        f"History of {base.lower()}",
        f"Future of {base.lower()}",
    ]
    return random.choice(templates)


def _assign_complexity(query: str) -> str:
    """Assign computational complexity to a query."""
    lower = query.lower()
    if any(word in lower for word in ["simple", "hi", "hello", "ok", "thanks", "bye"]):
        return "simple"
    elif any(word in lower for word in ["explain", "compare", "analyze", "detailed", "complete"]):
        return "complex"
    elif any(word in lower for word in ["long", "comprehensive", "full", "entire"]):
        return "long_context"
    return "normal"


def get_complexity_delay(complexity: str) -> int:
    """Get simulated LLM delay for a query complexity tier."""
    delays = {
        "simple": int(os.getenv("MOCK_LLM_DELAY_SIMPLE_MS", "300")),
        "normal": int(os.getenv("MOCK_LLM_DELAY_NORMAL_MS", "700")),
        "complex": int(os.getenv("MOCK_LLM_DELAY_COMPLEX_MS", "1200")),
        "long_context": int(os.getenv("MOCK_LLM_DELAY_LONG_MS", "2000")),
    }
    return delays.get(complexity, delays["normal"])


def save_workload(queries: List[Dict[str, Any]], path: str) -> None:
    """Save workload to CSV."""
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "type", "text", "base", "complexity"])
        writer.writeheader()
        for q in queries:
            writer.writerow({
                "id": q["id"],
                "type": q["type"],
                "text": q["text"],
                "base": q["base"],
                "complexity": q.get("complexity", "normal"),
            })
