# Sonata LLM reranking: production-path validation

Run: `20261004T085145Z`. The run calls the production service search method, uses its unchanged Vector Top-10, and executes retrieval only (no answer generation).

| Metric | Vector-only M6 baseline | Production service after |
|---|---:|---:|
| Hit@1 | 4/11 (36.4%) | 9/11 (81.8%) |
| Hit@3 | 8/11 (72.7%) | 11/11 (100.0%) |
| Hit@5 | 9/11 (81.8%) | 11/11 (100.0%) |
| Hit@10 | 11/11 (100.0%) | 11/11 (100.0%) |
| MRR@5 | 0.5333 | 0.9091 |
| MRR@10 | 0.5576 | 0.9091 |

- Vector candidates per question: 10; candidate sets match M6 CSV on all questions: True.
- Reranker: gpt-5.6-luna. Mean API rerank latency: 3.291s; mean total search latency: 3.765s.
- Mean input/output tokens: 4172.8/237.9; requests 11; retries 0; fallbacks 0.
- M6-05: 6 → 2.
- M6-11: 10 → 1.
- This 11-question set was used during development and does not establish accuracy on unseen questions.
