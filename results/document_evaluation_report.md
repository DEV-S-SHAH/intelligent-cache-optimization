# Document & PDF QA Caching Evaluation Report

## Overview
Evaluated retrieval QA performance over enterprise policy documents including:
- **PDF**: `data/sample_policy.pdf` (Global Enterprise AI & Cloud Security Policy)
- **Text**: `data/employee_handbook.txt`, `data/expense_policy.txt`, `data/remote_work_policy.txt`, `data/security_policy.txt`

## Performance Comparison

| Metric | Without Cache | Traditional Exact Cache | Intelligent Semantic Cache |
|---|---|---|---|
| **Total Query Time** | `6.68s` | `5.50s` | `**4.24s**` |
| **Mean Latency** | `417.7ms` | `343.3ms` | `**264.7ms**` |
| **Hit Rate** | `0.0%` | `18.8%` | `**37.5%**` |
| **Exact Hits** | `0` | `3` | `3` |
| **Semantic Hits** | `0` | `0` | `**3**` |
| **Speedup Factor** | `1.0x` | `1.22x` | `**1.58x**` |

## Summary
- **Paraphrase Recognition**: Semantic caching successfully captured paraphrased document questions from the PDF and text documents that exact matching missed completely.
- **Latency Reduction**: Mean response latency dropped from `417.7ms` to `**264.7ms**`.
