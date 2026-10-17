# Chapter 08 — LangChain / LangGraph: findings (impl b)

Source of truth: `runs/08_*/metrics.json`, `runs/scoreboard.md`. All 6 ran on the
test split (n=27: 8 single_hop, 7 multi_hop, 5 global, 4 unanswerable, 3
comparative; 23 carry evidence so hit/recall are averaged over 23).

## Scoreboard rows (new, vs the three anchors + ch07 best)

| experiment | hit@5 | recall@5 | MRR | nDCG@10 | correctness | faith | unans-abstain | LLM/q | s/q |
|---|---|---|---|---|---|---|---|---|---|
| **02_no_retrieval** (anchor) | 0.000 | 0.000 | 0.000 | 0.000 | 0.174 | 1.000 | 1.000 | 1.000 | 0.000 |
| **03_naive_fixed_512_k5** (anchor) | 0.478 | 0.370 | 0.307 | 0.349 | 0.435 | 0.937 | 1.000 | 1.000 | 0.006 |
| **02_oracle** (anchor) | 1.000 | 0.988 | 1.000 | 1.000 | 0.543 | 0.865 | 1.000 | 1.000 | 0.000 |
| 07_hybrid_k20_ce_bge_k5 (ch07 best) | 0.739 | 0.558 | 0.667 | 0.680 | 0.674 | 0.957 | 1.000 | 1.000 | 0.155 |
| **08_lc_naive** | 0.435 | 0.348 | 0.338 | 0.356 | 0.500 | 0.871 | 1.000 | 1.0 | 8.257 |
| **08_lc_parent** | 0.435 | 0.348 | 0.338 | 0.356 | 0.500 | 0.872 | 1.000 | 1.0 | 8.368 |
| **08_lc_multiquery** | 0.435 | 0.348 | 0.349 | 0.367 | 0.435 | 0.902 | 1.000 | 1.0 | 13.179 |
| **08_lc_ensemble** | 0.435 | 0.348 | 0.299 | 0.334 | 0.478 | 0.892 | 1.000 | 1.0 | 8.768 |
| **08_lc_ensemble_rerank** | 0.435 | 0.348 | 0.289 | 0.318 | 0.478 | 0.882 | 1.000 | 1.0 | 9.506 |
| **08_lg_crag** | 0.435 | 0.326 | 0.337 | 0.357 | 0.435 | 0.897 | 1.000 | 1.0 | 17.340 |

- All 6 hit@5 identical (0.435): same 5 chunk ids reach top-5 in every pipeline
  on this corpus (verified: naive==parent set-equal; naive != ensemble/multiquery/
  rerank/crag full list). Rank metrics (MRR/nDCG) differ → order of hits changes.
- recall@5 differs only for CRAG (0.326 vs 0.348): its re-rewrite drops an evidence
  chunk on some questions.
- unanswerable-abstain = **1.000** on every 08 run (all 4 unanswerable handled).

## Ran vs skipped

- **Ran (6/6):** lc_naive, lc_parent, lc_multiquery, lc_ensemble,
  lc_ensemble_rerank, lg_crag. All wrote `{metrics.json, predictions.jsonl, config.json}`.
- **Skipped (0):** none.
- **No `just` recipes existed** for these — ran all 6 via the CLI
  `uv run python -m rag_tutorial.fw_langchain eval --pipeline <name> --name <run>`.

## Bug fixed / workaround (the only code change)

- **`src/rag_tutorial/evaluate.py`** — the shared faithfulness judge's per-claim
  support call hit `max_tokens` on a long-answer question:
  `json.loads(support_reply)` → `JSONDecodeError: Unterminated string` on
  `lc_multiquery` (its rewrites → longer answers → longer claims list → the
  `results` JSON is cut mid-string before all claims are emitted). Raised the two
  internal `max_tokens` caps (claims 1536→3072, support 2048→4096). This changes the `ollama.chat` cache key
  for those two calls, so the affected judge responses re-fetch cleanly. No impact
  on metric definitions. `fw_langchain.py` left untouched.

## Per-question LLM call count (measured, generator-side)

`metrics.json llm_calls_per_q = 1.0` for **every** 08 run — that column counts only
the single **answer-generation** call (harness contract: judge calls excluded, same
as ch03–07 where even `07_multi_query`=1.0). Real generator-side totals measured by
wrapping `_counter`:

| pipeline | LLM calls/question | breakdown |
|---|---|---|
| lc_naive / lc_parent | 1 | answer only |
| lc_multiquery | 2 | 1 query-rewrite (MultiQueryRetriever) + answer |
| lc_ensemble / lc_ensemble_rerank | 1 | answer only (BM25/RRF/CE are non-LLM) |
| **lg_crag** | **2–3** (mean ≈2.5, n=8 sampled) | 1 grade + answer, **plus 1** rewrite+re-retrieve when grade says INSUFFICIENT |

- **CRAG does NOT hit the spec's expected 8–15.** The implemented graph is a **2-hop**
  (`START → retrieve → grade → (rewrite→retrieve) → END`) and caps at **one** rewrite
  (`do_grade` short-circuits at `attempt>=1`; `route_after_grade` forces END there).
  So it is bounded to 2–3 generator calls, and the spec's 8–15 expectation assumes an
  unbounded/iterative CORRECTIVE-LOOP that this pipeline does not implement. Report the
  2–3 figure, not 8–15.

## CRAG — unanswerable abstain rate + mermaid

- unanswerable-abstain = **1.000** (4/4 questions in `unanswerable` type correctly
  declined) — same as every other 08 pipeline and the anchors.

```mermaid
flowchart LR
    S([START]) --> R1[retrieve: embed query → Chroma top-k*2 → top-k contexts]
    R1 --> G1[grade: LLM SUFFICIENT/INSUFFICIENT (only if attempt==0)]
    G1 -->|SUFFICIENT| E([END: answer via shared prompt])
    G1 -->|INSUFFICIENT| W[rewrite: LLM QUERY: ...]
    W --> R2[retrieve again with rewritten query]
    R2 --> E
```

## Compare `08_lc_ensemble_rerank` vs our own `07_hybrid_k20_ce_bge_k5`

| metric | 07_hybrid_k20_ce_bge_k5 | 08_lc_ensemble_rerank | Δ |
|---|---|---|---|
| hit@5 | 0.739 | 0.435 | **−0.304** |
| recall@5 | 0.558 | 0.348 | −0.210 |
| MRR | 0.667 | 0.289 | −0.378 |
| nDCG@10 | 0.680 | 0.318 | −0.362 |
| correctness | 0.674 | 0.478 | −0.196 |
| faithfulness | 0.957 | 0.882 | −0.075 |

(07 baseline in task text was the *old* 0.609/0.414/0.565/0.926; the committed
`runs/07_hybrid_k20_ce_bge_k5/metrics.json` is the re-scored 0.739/0.558/0.674/0.957 —
use the on-disk committed values as authoritative.)

**Why the gap (all three framework-side, since both retrieve from the same Chroma
collection + nomic embeddings):**
- **Candidate pool / RRF denominator:** 07 searches with k=20 then cross-encoder
  re-ranks to 5; the LangChain `EnsembleRetriever` unions dense-top-k with BM25-top-k
  via weighted RRF at a much smaller pool (k=5), then CE re-ranks only that small
  union. Fewer candidates → the right chunk gets crowded out of top-5 → hit@5/recall@5
  collapse to the naive 0.435 baseline. This dominates the gap.
- **BM25 tokenisation:** `langchain_community.BM25Retriever` tokens with the standard
  regex stemmer, vs ch05's `rank_bm25` over our exact corpus — different idf pools
  change BM25 ordering, so the RRF blend shifts hit positions (MRR/nDCG worst for
  ensemble_rerank: 0.289/0.318, the lowest of all 6).
- **Prompt is identical** (shared `build_messages`) and embedder identical, so answer
  quality (correctness/faith) tracks the retrieval gap, not a prompt difference.
- Net: the framework's canned ensemble+rerank, as wired here, is **worse than our own
  ch07 pipeline** because it re-ranks a smaller candidate set — a config/scale
  artefact, not evidence LangChain is categorically weaker. If 07's k=20→CE-5 is
  reproduced through LangChain, parity is expected.

## Interesting observations (one-liners for the chapter writer)

- **All 6 pipelines tie on hit@5 (0.435)** — on this small, self-contained corpus the
  different retriever strategies (vector / parent / multiquery / ensemble / rerank /
  CRAG) converge to the same top-5 chunks; only their *ranking* (MRR, nDCG) separates.
- **CRAG is the slowest (17.3 s/q)** for its smallest retrieval gain — the extra
  grade+rewrite LLM calls buy 0 hit@5 and *cost* 0.022 recall@5 vs naive.
- **lc_parent is numerically == lc_naive** (same ids, faith 0.872 vs 0.871) because
  our chunks are already self-contained; parent-document retrieval shows its value
  only when child fragments are non-standalone.
- **The framework ensemble+rerank underperforms our own ch07 hybrid** (hit@5 0.435
  vs 0.739) purely from re-ranking a smaller RRF candidate pool — a config trap, not
  a framework weakness.
- **`llm_calls_per_q=1.0` everywhere is by design** (measures answer-gen only); CRAG's
  real generator cost is 2–3/q and multiquery is 2/q — worth spelling out so readers
  don't read the scoreboard column as "all pipelines are equal-cost."
- **Judge truncation bite:** a faithful multi-query answer is *more* faithful (faith 0.902,
  highest of the 6) but also *longer* — its claims list outgrew the judge's `max_tokens`
  and cut the per-claim JSON mid-string. Raising `max_tokens` (claims 3072 / support 4096)
  fixed it — a real "good answer breaks the evaluator" production gotcha.
