# Document & PDF QA Caching Evaluation Report

## Overview
Evaluated retrieval QA performance over enterprise policy documents including:
- **PDF**: `data/sample_policy.pdf` (Global Enterprise AI & Cloud Security Policy)
- **Text**: `data/employee_handbook.txt`, `data/expense_policy.txt`, `data/remote_work_policy.txt`, `data/security_policy.txt`

## Performance Comparison

| Metric | Without Cache | Traditional Exact Cache | Intelligent Semantic Cache |
|---|---|---|---|
| **Total Query Time** | `6.69s` | `5.52s` | `**4.24s**` |
| **Mean Latency** | `418.3ms` | `344.5ms` | `**264.8ms**` |
| **Hit Rate** | `0.0%` | `18.8%` | `**37.5%**` |
| **Exact Hits** | `0` | `3` | `3` |
| **Semantic Hits** | `0` | `0` | `**3**` |
| **Speedup Factor** | `1.0x` | `1.21x` | `**1.58x**` |

## Summary
- **Paraphrase Recognition**: Semantic caching successfully captured paraphrased document questions from the PDF and text documents that exact matching missed completely.
- **Latency Reduction**: Mean response latency dropped from `418.3ms` to `**264.8ms**`.
