# Chapter 07 — Reranking & Query Transform: Findings

Baseline for all comparisons: **`05_hybrid_rrf_k5`** (parent_child chunks 800/160, dense `nomic-embed-text` + `bm25s`, RRF k_each=20, k=5).
`corr` = answer correctness, `faith` = faithfulness, `hit5/rec5` = retrieval quality, `LLM/q` + `s/q` = cost.

## 1. Master metrics table

| run | hit5 | rec5 | corr | faith | abst | LLM/q | s/q |
|---|---|---|---|---|---|---|---|
| 05_hybrid_rrf_k5 (baseline) | 0.609 | 0.414 | 0.565 | 0.926 | 1.00 | 1.0 | 6.9 |
| 07_hybrid_k20_flashrank_k5 | **0.696** | 0.479 | 0.522 | 0.934 | 1.00 | 1.0 | **0.0** |
| 07_hybrid_k20_ce_bge_k5 | 0.739 | 0.558 | **0.674** | **0.957** | 1.00 | 1.0 | 0.2 |
| 07_hybrid_k20_ce_minilm_k5 | 0.696 | 0.479 | 0.478 | 0.950 | 1.00 | 1.0 | 0.5 |
| 07_hybrid_k20_llm_listwise_k5 | **0.783** | **0.638** | 0.609 | 0.945 | 1.00 | 1.0 | 18.4 |
| 07_hybrid_k20_colbert_k5 | 0.435 | 0.319 | 0.391 | 0.951 | 1.00 | 1.0 | 44.2 |
| 07_multi_query | 0.652 | 0.477 | 0.587 | 0.937 | 1.00 | 1.0 | 72.9 |
| 07_hyde | 0.652 | 0.501 | 0.565 | 0.927 | 1.00 | 1.0 | 122.1 |
| 07_step_back | 0.565 | 0.429 | 0.543 | 0.936 | 1.00 | 1.0 | 59.1 |
| 07_decompose | 0.609 | 0.480 | 0.522 | 0.930 | 1.00 | 1.0 | 82.3 |
| 07_compress | 0.609 | 0.414 | 0.304 | 0.904 | 1.00 | 6.0 | 7.4 |
| 07_litm_reorder | 0.609 | 0.414 | **0.717** | 0.917 | 1.00 | 1.0 | 41.9 |
| 07_best_combo | 0.652 | 0.506 | 0.587 | 0.931 | 1.00 | 1.0 | 5.0 |

Best-in-class per axis: **hit5** = llm_listwise (0.783) · **corr** = litm_reorder (0.717) · **faith** = ce_bge (0.957) · **fastest** = flashrank (0.0 s/q).

## 2. k_each sweep (retrieval quality only, n=23)

| reranker | k_each | hit5 | rec5 | ndcg10 | mrr | s/q |
|---|---|---|---|---|---|---|
| cross-encoder-bge | 20 | 0.739 | 0.558 | 0.688 | 0.684 | 1.02 |
| cross-encoder-bge | 50 | **0.783** | 0.580 | 0.665 | 0.681 | 1.66 |
| cross-encoder-minilm | 20 | 0.696 | 0.479 | 0.600 | 0.588 | 0.29 |
| cross-encoder-minilm | 50 | 0.696 | **0.500** | 0.562 | 0.555 | 0.17 |
| flashrank | 20 | 0.696 | 0.479 | 0.554 | 0.516 | **0.05** |
| flashrank | 50 | 0.696 | 0.479 | 0.572 | 0.530 | 0.10 |

## 3. Per-type correctness (best_combo vs baseline) — `07_per_type.md`

| type | n | baseline | best_combo | delta |
|---|---|---|---|---|
| single_hop | 8 | 0.750 | 0.875 | **+0.125** |
| multi_hop | 7 | 0.357 | 0.571 | **+0.214** |
| comparative | 3 | 0.667 | 0.167 | **−0.500** |
| global | 5 | 0.500 | 0.400 | −0.100 |
| unanswerable | 4 | 1.000 (abstain) | 1.000 (abstain) | 0 |

## 4. Skipped / failed experiments & library issues

- **ColBERT loaded and ran** (model `colbert-v1` downloaded on first use; an earlier `answerai-colbert-small-v1` name was not found and was the cause of the first `No sentence-transformers model found` warning — a different model id is used in this run). It is the **worst** reranker: hit5 0.435, 44 s/q. ColBERT is a late-interaction model over long-token embeddings; against a parent_child + hybrid baseline it loses badly here and is far slower. Not worth keeping in the default path.
- **All 12 named experiments + sweep completed** — no hard-crash skips. `llm/q` is reported as the generation + judge calls (1.0) — reranker and transform calls are counted separately in `details` (see the `reranker_n_calls` field in each metrics.json).
- **ragatouille** is **not installed** — any RAGAToU-style retrieval path is not part of this chapter's measured set.
- **FlashRank** installed cleanly and runs 30–300× faster than the cross-encoders (~0.05 s/q).

## 5. 3–5 things worth remembering

1. **Retrieval quality ≠ answer correctness — and they can disagree strongly.** LITM reorder barely moves hit5 (0.609, baseline-tied) yet **jumps correctness from 0.565 → 0.717**, the single biggest correctness gain here. Reordering the *order the generator sees chunks* (put the most-relevant in the middle of the context) is a cheap, high-leverage answer-quality lever that retrieval metrics won't show you.
2. **LLM listwise reranking is the best retrieval ranker we measured (hit5 0.783, rec5 0.638)** but costs ~18 s/q and only lifts correctness to 0.609. It is a retrieval-quality tool, not an answer-quality tool — pair it with LITM reorder (that's `best_combo`) to get the benefit into correctness.
3. **Cross-encoder bge is the best cheap reranker**: hit5 0.739 @ k20 (→0.783 @ k50) and the **best faithfulness (0.957)** at 1.0 s/q. minilm ties flashrank on hit5 (0.696) but is ~5× slower for no gain. **bge at k_each=50 is the default pick for a production reranker on this corpus.**
4. **More candidates help the reranker — but only for the strongest model.** k_each 20→50 lifts bge hit5 0.739→0.783, yet leaves minilm's hit5 flat (0.696) and only nudges flashrank. A reranker's ceiling is set by the model, not the candidate pool size.
5. **Query transforms underperformed for this QA set.** HyDE (0.565), step-back (0.543), decompose (0.522), compress (0.304) all sit at or below baseline correctness, and step-back even *lowers* hit5 (0.565). These techniques pay off on long/ambiguous multi-intent queries; on our clear single-sentence test set they mainly add LLM cost (59–122 s/q) and dilute the original query. **Compress is a net loser** — it both lowers correctness (0.304) *and* faithfulness (0.904).
6. **`best_combo` (llm_listwise + LITM) is a solid, balanced default**: corr 0.587, hit5 0.652, faith 0.931 at only ~5 s/q. It wins big on single_hop (+0.125) and multi_hop (+0.214) vs baseline but **regresses hard on comparative (−0.500)** — 3-question sample, but a real signal that listwise reranking over-hallucinates on "which is X vs Y" questions.

**One-line takeaway:** the biggest free win is **LITM chunk reordering** (best correctness, cheap); the best retrieval-quality upgrade is **bge cross-encoder at k_each=50**; avoid **ColBERT** and **compress** on this corpus.
