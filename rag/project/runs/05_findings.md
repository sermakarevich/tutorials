# 05 findings (handoff for the chapter writeup)

## Setup
- Chunking fixed to chapter-04 best cheap strategy: **parent_child** (best ch04 row: hit@5 0.609, recall@5 0.493, MRR 0.433, nDCG@10 0.474; children index + parent-swap after retrieval). Chosen because it tops the ch04 scoreboard with plain Chroma + nomic, no extra LLM passes (unlike `04_contextual_512`), and beats markdown_512 / semantic / fixed-1024.
- Chat model qwen3.8:27b, embedder nomic-embed-text (768-d, cosine). Sweep ran on 23 questions; full evals on 27 (test split, incl. unanswerables).
- All experiments ran, none skipped. No library failed to install (bm25s 0.3.11, PyStemmer, qdrant-client, fastembed all present).
- Qdrant sparse vector uses **fastembed's `Qdrant/bm25`** sparse encoder (built-on-demand `Bm25Encoder`, ~10 MB download, `Modifier.IDF` weights) rather than pulling bm25s scores out by hand; bm25s itself is used for the standalone `BM25Retriever` and its hand-rolled hybrid fusion. Documented at `stores.py::_bm25_sparse_model`.

## Scoreboard rows (ch05 experiments next to anchors)

| experiment | hit@5 | recall@5 | MRR | nDCG@10 | correctness | faithfulness | unans-abstain | calls/q | s/q |
|---|---|---|---|---|---|---|---|---|---|
| 02_no_retrieval (anchor) | 0.000 | 0.000 | 0.000 | 0.000 | 0.174 | 1.000 | 1.000 | 1.0 | 0.0 |
| 03_naive_fixed_512_k5 (anchor) | 0.478 | 0.370 | 0.307 | 0.349 | 0.435 | 0.937 | 1.000 | 1.0 | 0.006 |
| 02_oracle (ceiling) | 1.000 | 0.988 | 1.000 | 1.000 | 0.543 | 0.865 | 1.000 | 1.0 | 0.0 |
| **05_bm25_k5** | **0.696** | 0.486 | 0.521 | **0.560** | 0.587 | 0.908 | 1.000 | 1.0 | 30.19 |
| 05_dense_k5 | 0.609 | 0.493 | 0.433 | 0.474 | 0.500 | 0.901 | 1.000 | 1.0 | 0.003 |
| 05_hybrid_rrf_k5 | 0.609 | 0.414 | 0.457 | 0.489 | 0.565 | 0.926 | 1.000 | 1.0 | 6.93 |
| 05_hybrid_weighted_k5 | 0.652 | **0.501** | 0.504 | 0.532 | 0.609 | 0.927 | 1.000 | 1.0 | 3.40 |
| 05_hybrid_rrf_k10 | 0.609 | 0.414 | 0.481 | 0.552 | **0.696** | 0.934 | 1.000 | 1.0 | 8.53 |
| 05_dense_mmr_k5 | 0.522 | 0.449 | 0.393 | 0.419 | 0.565 | 0.916 | 1.000 | 1.0 | 18.38 |
| 05_hybrid_rrf_filtered_k5 | 0.609 | 0.414 | 0.457 | 0.489 | 0.565 | 0.936 | 1.000 | 1.0 | 18.51 |
| 05_qdrant_native_hybrid_k5 | 0.565 | 0.471 | 0.500 | 0.506 | 0.652 | **0.943** | 1.000 | 1.0 | 14.53 |

Note: `llm_calls_per_q` in the scoreboard counts generation+judge calls (all 1.0/q here); retrieval itself needed 0–1 extra router call per question in the filtered run. `05_bm25_k5` s/q is inflated by the first-run bm25s index build (30.2 s); subsequent runs reuse `data/indexes/bm25/parent_child`.

## Routing/filter stats (05_hybrid_rrf_filtered_k5)
- Router asked on all 27 questions (27 router calls), fired a `{"paper": ...}` filter on **9/27 (33%)**.
- Retrieval metrics identical to unfiltered hybrid_rrf_k5 (hit 0.609 / recall 0.414 / MRR 0.457); faithfulness rose 0.926 → 0.936, correctness same 0.565. Net: neutral on this small corpus, positive on faithfulness.

## Retrieval-only k-sweep (23 questions, no generation) — `runs/05_retrieval_sweep.json`

| k | dense hit/recall/ndcg | bm25 hit/recall/ndcg | hybrid_rrf hit/recall/ndcg |
|---|---|---|---|
| 1 | 0.304 / 0.232 / 0.304 | **0.435** / **0.348** / **0.435** | 0.348 / 0.304 / 0.348 |
| 3 | 0.522 / 0.406 / 0.377 | 0.565 / 0.449 / 0.460 | **0.609** / **0.414** / **0.422** |
| 5 | 0.609 / 0.493 / 0.404 | **0.696** / 0.486 / **0.498** | 0.609 / 0.414 / 0.428 |
| 10 | 0.652 / 0.538 / 0.452 | 0.739 / 0.573 / **0.538** | **0.826** / **0.660** / 0.514 |
| 20 | 0.739 / 0.586 / 0.492 | 0.913 / 0.681 / 0.599 | 0.870 / **0.718** / 0.559 |

- MRR (full): dense 0.446, bm25 0.539, hybrid_rrf 0.483.
- Latency (mean s/question, retrieval only): dense 0.0018, bm25 0.0004, hybrid 0.0014.
- Plot: `runs/05_retrieval_sweep.png` (recall@k curves).

## Interesting observations (one-liners for the chapter)
- BM25 alone beats dense on hit@1 (0.435 vs 0.304) and hit@5 (0.696 vs 0.609) — exact-term questions (numbers, acronyms) are where dense retrieval loses.
- RRF fusion has recall *lower* than both inputs at k=5 (0.414 vs 0.493/0.486) but wins big on the long tail: recall@10 0.660 vs 0.538/0.573, recall@20 0.718 vs 0.586/0.681 — fusion diversifies coverage.
- MMR (λ=0.7) costs retrieval (hit@5 0.609 → 0.522) but lifts correctness 0.500 → 0.565: diversity pays off at generation, not at the metric table.
- Weighted min-max fusion (α=0.5) matches BM25's recall@5 (0.501) and beats it on correctness (0.609 vs 0.587) with half the s/q — RRF isn't the only reasonable fusion.
- Qdrant native hybrid (server-side RRF, prefetch + `FusionQuery`) lands mid-pack (correctness 0.652, faithfulness 0.943 = best) and serves in ~14 ms (0.014 s measured `query_points`); parity proves our client-side fusion was correct.
- LLM paper-router fires on only 1/3 of questions and changes nothing on this 4-paper corpus — filters matter at scale, not here.
