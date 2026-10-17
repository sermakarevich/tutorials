# Scoreboard analysis (all runs)

_65 runs. Baseline for deltas: `03_naive_fixed_512_k5`._

## What helped most (best run per technique family, ranked by gain)

| family | best run | correctness | delta vs naive | s/q | LLM calls/q | n runs |
|---|---|---|---|---|---|---|
| dspy | 10_dspy_zero_shot | 0.739 | +0.304 | 10.459 | 1.000 | 3 |
| framework-llamaindex | 09_li_subquestion | 0.739 | +0.304 | 450.074 | 5.185 | 10 |
| rerank | 07_litm_reorder | 0.717 | +0.283 | 41.907 | 1.000 | 6 |
| framework-haystack | 10_hs_hybrid | 0.696 | +0.261 | 11.478 | 1.000 | 2 |
| hybrid | 05_hybrid_rrf_k10 | 0.696 | +0.261 | 8.530 | 1.000 | 5 |
| app | 12_openwebui_hybrid_rerank | 0.587 | +0.152 | 19.796 | 1.000 | 2 |
| best-combo | 07_best_combo | 0.587 | +0.152 | 4.950 | 1.000 | 1 |
| query-transform | 07_multi_query | 0.587 | +0.152 | 72.873 | 1.000 | 4 |
| sparse | 05_bm25_k5 | 0.587 | +0.152 | 30.190 | 1.000 | 1 |
| diversity | 05_dense_mmr_k5 | 0.565 | +0.130 | 18.380 | 1.000 | 1 |
| anchor | 02_oracle | 0.543 | +0.109 | 0.000 | 1.000 | 5 |
| chunking | 04_sentence_window | 0.543 | +0.109 | 2.775 | 1.000 | 10 |
| graph-raptor | 11_raptor_collapsed_k10 | 0.522 | +0.087 | 12.765 | 1.000 | 2 |
| dense | 05_dense_k5 | 0.500 | +0.065 | 0.003 | 1.000 | 1 |
| framework-langchain | 08_lc_naive | 0.500 | +0.065 | 8.257 | 1.000 | 5 |
| agentic | 08_lg_crag | 0.435 | +0.000 | 17.340 | 1.000 | 1 |
| compression | 07_compress | 0.304 | -0.130 | 7.396 | 6.000 | 1 |
| graph-lightrag | 11_lightrag_global | 0.130 | -0.304 | 0.988 | 1.000 | 5 |

## Pareto frontier (no other run is better on both quality and latency)

| run | correctness | s/q |
|---|---|---|
| 10_dspy_zero_shot | 0.739 | 10.459 |
| 05_hybrid_rrf_k10 | 0.696 | 8.530 |
| 07_hybrid_k20_ce_bge_k5 | 0.674 | 0.155 |
| 02_oracle | 0.543 | 0.000 |
| 02_no_retrieval | 0.174 | 0.000 |

## Correctness by question type (selected runs)

| run | comparative | global | multi_hop | single_hop |
|---|---|---|---|---|
| 03_naive_fixed_512_k5 | 0.333 | 0.300 | 0.286 | 0.688 |
| 07_hybrid_k20_ce_bge_k5 | 0.167 | 0.400 | 0.714 | 1.000 |
| 09_li_fusion_rerank | 0.167 | 0.500 | 0.571 | 1.000 |
| 10_dspy_zero_shot | 0.167 | 0.500 | 0.857 | 1.000 |
| 08_lg_crag | 0.167 | 0.300 | 0.500 | 0.562 |
| 11_lightrag_hybrid | 0.000 | 0.000 | 0.071 | 0.125 |

## Plots

- Correctness vs seconds/question: `13_quality_vs_latency.png`
- Correctness vs LLM calls/question: `13_correctness_vs_calls.png`
- Recall@5 vs correctness: `13_recall_vs_correctness.png`
- Per-type heatmap: `13_per_type_heatmap.png`
