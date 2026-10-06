# Sonata synthetic holdout: Vector-only vs LLM reranking

- Run: `20261004T095242Z`; question set frozen at `2026-10-04T09:48:31.082117+00:00`.
- Frozen set SHA-256: `ee54c3ee5810cb4dab2c74461e71f5b03fa225459dd7d3f1e0e201801ea8c2b9`.
- New synthetic holdout: 50 questions, stratified from the current Sonata 2026 chunk corpus. This is separate from the historical M6 development set.
- Reranker: production `CarManualSearchService.search_manual_with_metadata`, model `gpt-5.6-luna`.
- Candidate policy: each question uses one unchanged Vector Top-10; the reranker only permutes those candidates.

## Overall results

| Metric | Vector Only | LLM Rerank |
|---|---:|---:|
| Hit@1 | 23/50 (46.0%) | 38/50 (76.0%) |
| Hit@3 | 37/50 (74.0%) | 44/50 (88.0%) |
| Hit@5 | 43/50 (86.0%) | 44/50 (88.0%) |
| Hit@10 | 44/50 (88.0%) | 44/50 (88.0%) |
| MRR@5 | 0.6190 | 0.8200 |
| MRR@10 | 0.6219 | 0.8200 |

## Candidate and ranking outcomes

- Vector Top-10 candidate misses: 6.
- Ranking failures (candidate present but reranked below Top-5): 0.
- Successful Top-5 after reranking: 44.
- All candidate sets identical before/after: True.

## Largest rank movements

| Question | Chapter | Before | After | Rank rise |
|---|---:|---:|---:|---:|
| U50-002 | 1 | 7 | 1 | +6 |
| U50-017 | 4 | 5 | 2 | +3 |
| U50-031 | 6 | 4 | 1 | +3 |
| U50-032 | 6 | 4 | 1 | +3 |
| U50-033 | 6 | 4 | 1 | +3 |

| Question | Chapter | Before | After | Rank fall |
|---|---:|---:|---:|---:|
| U50-029 | 6 | 1 | 2 | -1 |
| U50-001 | 1 | 2 | 2 | 0 |
| U50-003 | 1 | 1 | 1 | 0 |
| U50-007 | 2 | 1 | 1 | 0 |
| U50-008 | 2 | 1 | 1 | 0 |

## Chapter metrics

| Chapter | Questions | Vector Hit@5 | Vector MRR@5 | Rerank Hit@5 | Rerank MRR@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 3/5 (60.0%) | 0.3667 | 4/5 (80.0%) | 0.7000 |
| 2 | 5 | 2/5 (40.0%) | 0.4000 | 2/5 (40.0%) | 0.4000 |
| 3 | 6 | 6/6 (100.0%) | 0.5556 | 6/6 (100.0%) | 1.0000 |
| 4 | 5 | 5/5 (100.0%) | 0.7067 | 5/5 (100.0%) | 0.9000 |
| 5 | 6 | 6/6 (100.0%) | 1.0000 | 6/6 (100.0%) | 1.0000 |
| 6 | 6 | 5/6 (83.3%) | 0.4583 | 5/6 (83.3%) | 0.7500 |
| 7 | 6 | 5/6 (83.3%) | 0.5417 | 5/6 (83.3%) | 0.7500 |
| 8 | 5 | 5/5 (100.0%) | 0.7500 | 5/5 (100.0%) | 1.0000 |
| 9 | 6 | 6/6 (100.0%) | 0.7500 | 6/6 (100.0%) | 0.8333 |

## Question-type metrics

| Type | Questions | Vector Hit@5 | Vector MRR@5 | Rerank Hit@5 | Rerank MRR@5 |
|---|---:|---:|---:|---:|---:|
| condition | 10 | 9/10 (90.0%) | 0.8500 | 9/10 (90.0%) | 0.8500 |
| feature | 6 | 4/6 (66.7%) | 0.5833 | 4/6 (66.7%) | 0.5833 |
| maintenance | 4 | 3/4 (75.0%) | 0.4583 | 3/4 (75.0%) | 0.7500 |
| procedure | 12 | 12/12 (100.0%) | 0.6736 | 12/12 (100.0%) | 1.0000 |
| setting | 3 | 3/3 (100.0%) | 0.3611 | 3/3 (100.0%) | 0.8333 |
| troubleshooting | 4 | 4/4 (100.0%) | 0.7500 | 4/4 (100.0%) | 1.0000 |
| warning | 11 | 8/11 (72.7%) | 0.4500 | 9/11 (81.8%) | 0.6818 |

## Latency and usage

- Requests: 51; input tokens: 201207; output tokens: 12877; total tokens: 214084.
- Mean input/output tokens per question: 4024.1/257.5.
- Mean/min/max rerank latency: 3.404/2.209/9.345s.
- Mean total search latency: 3.807s; total 50-question elapsed time: 190.363s.
- Retry count: 1; rerank error attempts: 1; fallbacks: 0.

## Comparison and interpretation

Historical M6 development set (11 questions): Vector Hit@5 81.8%, MRR@5 0.5333; production LLM rerank Hit@5 100%, MRR@5 0.9091. These historical results remain separate and are not pooled with this holdout.
This 50-question set is generated synthetically from sampled manual chunks; it is not equivalent to 50 real user questions and does not prove generalization to actual user traffic.

**Verdict: A. unseen synthetic holdout에서도 명확한 개선.**
