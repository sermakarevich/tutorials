# Chapter 11 findings (impl task handoff — bullets only)

## What ran
- RAPTOR build: OK (1942 ch05-child leaves -> embed nomic-embed-text -> agglomerative/cosine/average-linkage, NOT UMAP+GMM: avoids numba/pynndescent deps, deterministic; target cluster size 10 -> LLM summary per cluster -> embed summaries -> recurse until <=5 top nodes).
- RAPTOR eval k5 + k10: OK (27 test questions).
- LightRAG index (lightrag-hku 1.5.7): OK, 12/12 docs, resumable working dir, single run 12:57-15:0x (~122 min). No restart needed.
- LightRAG eval v1 (5 modes): OK but mapping flawed -> superseded, not on scoreboard separately (same predictions dirs overwritten by v2).
- LightRAG eval v2 (5 modes, order-aware mapping): OK, all rows on scoreboard.
- Per-type table + chart: OK, 11 rows, 0 skipped.
- Tests: 10/10 pass (`tests/test_11_graph.py`).
- Skipped: nothing. HippoRAG not run (per spec, writeup-only). MS GraphRAG not run (per spec, covered by graph_rag tutorial).

## Library / install notes
- `lightrag-hku==1.5.7` installed into `lightrag` dependency group OK; no install failure.
- `scikit-learn` used for RAPTOR clustering (already a dependency? added if missing — check pyproject diff at commit).
- No Neo4j, no reranker: LightRAG logs "Rerank is enabled but no rerank model is configured" warning on every query; retrieval still returns.

## RAPTOR numbers
- Build: leaves 1942, summaries 215, levels {0:1942, 1:194, 2:19, 3:2}, depth 3, 215 summary LLM calls, 51.3 min wall, 217621120 B index (Chroma collection `raptor_11_all`, 2157 nodes, each with `level` metadata).
- k5: correctness 0.4130, hit@5 0.435, recall@5 0.326, mrr 0.230, ndcg@10 0.280, faithfulness 0.896, abstain 1.0, llm/q 1.0.
- k10: correctness 0.5217, hit@5 0.435, recall@5 0.326, hit@10 0.565, recall@10 0.414, mrr 0.244, ndcg@10 0.319, faithfulness 0.917, abstain 1.0, llm/q 1.0, s/q 12.8. (k5 s/q 0.0 = fully-cached re-run artifact.)
- Metric caveat: summary nodes count as retrieved context; judged relevant only if they contain the evidence quote (substring/token-overlap) — usually they don't, so collapsed-tree retrieval metrics understate summary usefulness; correctness is the fairer comparator.

## LightRAG index numbers
- 12 docs, 872030 chars, 211 LightRAG chunks (1200/100 splitter), wall 121.97 min, LLM calls 497, embed_texts 6091.
- Graph: 3135 entities, 2303 relations, 0 community files at index end (no `community_reports.json`/`kv_store_community_reports.json`; communities materialize lazily at global-query time, if at all).
- Working dir 41 MB total; biggest files: vdb_entities.json 20.8 MB, vdb_relationships.json 15.1 MB, kv_store_llm_response_cache.json 8.8 MB.
- Index log noise: many `Complete delimiter can not be found in extraction result` warnings and `LLM output format error ... RELATION` lines — entity/relation extraction is lossy on this corpus.
- Slow part is nano-vectordb upserts (25-200 s per relation batch), not LLM calls.

## LightRAG eval numbers (v2, final)
| mode | corr | hit@5 | rec@5 | mrr | ndcg@10 | faith | abst | llm/q | s/q |
| naive | 0.109 | 0.087 | 0.065 | 0.087 | 0.087 | 0.972 | 1.0 | 1.0 | 1.7 |
| local | 0.109 | 0.087 | 0.065 | 0.087 | 0.087 | 0.973 | 1.0 | 1.0* | 0.7 |
| global | 0.130 | 0.087 | 0.065 | 0.087 | 0.087 | 0.966 | 1.0 | 1.0* | 1.0 |
| hybrid | 0.065 | 0.087 | 0.065 | 0.087 | 0.087 | 0.979 | 1.0 | 1.0* | 0.6 |
| mix | 0.065 | 0.087 | 0.065 | 0.087 | 0.087 | 0.979 | 1.0 | 1.0* | 0.2 |
- `*` llm/q 1.0 for graph modes is a cache artifact: v1 (uncached) measured 2.0/q (1 keyword-extraction + 1 answer). True uncached cost = 2/q for local/global/hybrid/mix, 1/q naive. v2 retrieval made 0 LLM calls because LightRAG's internal `kv_store_llm_response_cache.json` served keyword extraction (verified by probe: novel question -> 1 call).
- hit@10 == hit@5 by construction: harness maps exactly 5 chunk ids per query (retrieve k=5 default), so @10 has no extra candidates. RAPTOR k10 differs (retrieves 10).
- Only 2/27 questions hit in ANY mode (single_hop_000, multi_hop_004); both hit in ALL 5 modes.

## Mapping quality (the spec's "record how well that mapping works")
- Method v1 (superseded): pure word-overlap over ~100 KB context -> saturated (top1_score exactly 1.5 and n_strong 10/10 for all 135 queries) yet hit@5 0.087. Ranking was meaningless.
- Method v2 (final): parse ```json chunk blocks (one JSON obj/line, streaming raw_decode, robust to embedded newlines), preserve LightRAG's chunk rank; leaves contained verbatim sort by chunk rank, rest backfill by overlap. `reference_id` is ALWAYS empty, so no direct id join exists — text matching is the only bridge.
- Mean LightRAG chunks parsed per query: naive 16.9, local 14.6, global 14.2, hybrid 11.7, mix 11.7. Mean context chars: naive 99136, local 117269, global 122332, hybrid 122184, mix 122159.
- Quote-in-context diagnostic (all 47 evidence quotes x 5 modes): naive 17/47, local 15/47, global 16/47, hybrid 9/47, mix 8/47 present verbatim anywhere in the returned context. So ~2/3 of misses are LightRAG retrieval itself, not the bridge.
- In-context quotes spread across chunk ranks 0-19 (naive positions: 0,0,0,1,3,4,6,8,8,10,12,15,16,16,16,19); projecting ~15 chunks to 5 ids caps recall even with a perfect bridge.
- Graph modes (hybrid/mix) return FEWER evidence-bearing contexts than naive (8-9 vs 17/47) — entity/relation prose displaces chunks but has no chunk-id counterpart.
- All modes share near-identical top vector chunk (verified on 1 probe question: same 6117-char chunk ranked [0] in naive/local/mix; 4/5 mapped ids identical) — modes differ in surrounding prose, not core chunk ranking, on this corpus.

## Per-type correctness (test: 8 single / 7 multi / 3 comp / 5 global / 4 unanswerable)
| exp | single | multi | comp | global | unanswerable* |
| 05_hybrid_rrf_k5 | 0.75 | 0.3571 | 0.6667 | 0.5 | 1.0 |
| 07_best_combo | 0.875 | 0.5714 | 0.1667 | 0.4 | 1.0 |
| 08_lg_crag | 0.5625 | 0.5 | 0.1667 | 0.3 | 1.0 |
| 09_li_router | 0.625 | 0.4286 | 0.5 | 0.3 | 1.0 |
| 11_raptor_k5 | 0.625 | 0.2143 | 0.1667 | 0.5 | 1.0 |
| 11_raptor_k10 | 0.6875 | 0.4286 | 0.3333 | 0.5 | 1.0 |
| 11_lr_naive | 0.25 | 0.0714 | 0.0 | 0.0 | 1.0 |
| 11_lr_local | 0.25 | 0.0 | 0.0 | 0.1 | 1.0 |
| 11_lr_global | 0.25 | 0.0714 | 0.0 | 0.1 | 1.0 |
| 11_lr_hybrid | 0.125 | 0.0714 | 0.0 | 0.0 | 1.0 |
| 11_lr_mix | 0.125 | 0.0714 | 0.0 | 0.0 | 1.0 |
- `*` unanswerable = abstain rate, not correctness. Chart: `runs/11_per_type.png`. JSON: `runs/11_per_type.json` (includes indexing-cost table).

## Indexing cost table
| system | LLM calls | minutes | size/chunks |
| baseline (03 naive 512/128) | 0 | 0.83 | 591 chunks |
| contextual (04) | 670 (estimate: 1/chunk) | 20.79 | 670 chunks |
| RAPTOR (11) | 215 | 51.3 | 2157 nodes / 207 MB |
| LightRAG (11) | 497 | 122.0 | 3135 ent + 2303 rel / 41 MB working dir |

## Scoreboard deltas (correctness, test split)
- Best prior (07_best_combo) 0.587 > RAPTOR k10 0.522 > 09 router 0.478 > 08 CRAG 0.435 > RAPTOR k5 0.413 >> LightRAG 0.065-0.130.
- RAPTOR k10 nearly matches best prior on global questions (0.5 tie with 05 baseline) but trails on multi-hop (0.43 vs 0.57).
- LightRAG faithfulness highest on chart (0.97-0.98) — artifact of short answers from thin context, not quality; correctness near floor.

## Interesting observations (for chapter writer)
- LightRAG's graph modes underperform its own naive mode on chunk-presence (mix 8/47 vs naive 17/47 quotes in context) — graph overhead buys nothing measurable here.
- RAPTOR k10 correctness (0.52) beats its k5 (0.41) while hit@5 is identical (0.435) — the extra 5 leaves help the generator without moving hit@k.
- All 11 rows abstain 1.0 on unanswerable — abstention behavior is prompt-driven, unaffected by retriever choice.
- LightRAG eval is ~10x faster per question than the 09 router (0.2-1.7 s/q vs 165 s/q) because everything is cache-hot; uncached it would be dominated by Ollama QA as usual.
- Async teardown tracebacks (`no running event loop` from lightrag/utils.py workers) after eval exit are harmless noise; all metrics are written before them.
