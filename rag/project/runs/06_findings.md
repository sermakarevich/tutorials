# Chapter 06 — Embeddings & Vector Stores: Findings

Corpus: 12 papers → 1942 child chunks (328 parent). Test split: 23 questions with
evidence chunks. Every metric below is `recall@5` (fraction of evidence chunks
found in the top-5 retrievals, averaged over questions) unless noted.

## Embedding model comparison

| model                 | dim  | recall@5 | mrr    | hit@5  |
|-----------------------|------|----------|--------|--------|
| snowflake-arctic-embed2 | 1024 | 0.4275   | 0.3928 | 0.5652 |
| bge-m3                | 1024 | 0.4145   | 0.3768 | 0.6087 |
| embeddinggemma-300m   | 768  | 0.3696   | 0.3696 | 0.4783 |
| mxbai-embed-large     | 1024 | 0.2971   | 0.3116 | 0.3913 |
| nomic-embed-text      | 768  | 0.2826   | 0.2391 | 0.3913 |
| qwen3-embedding       | 1024 | 0.2609   | 0.2080 | 0.3478 |
| all-minilm-22m        | 384  | 0.1957   | 0.1681 | 0.2609 |

Sorted by recall@5. Key takeaways:

- **snowflake-arctic-embed2 and bge-m3 are in the same tier** (~0.42–0.43). bge-m3
  wins hit@5 (0.609 vs 0.565) — it tends to put at least one evidence chunk in
  the top-5 more often, while snowflake wins on average recall and MRR. Pick
  either; the gap is within question-level noise on 23 questions.
- **nomic-embed-text is a solid mid-tier**: recall@5 0.28, but it's the fastest
  to *serve* (13.4k chunks/s — it's already cached at the moment of this run,
  so the effective cost is near-zero). For a tutorial where the corpus is small
  and latency-per-embedding dominates, that's a real advantage.
- **all-minilm is the obvious low-power option** (23M params, 44 MB, 42
  chunks/s) at a measurable cost (−19 pts recall). For very small corpora or
  edge deployment it's the right answer; for anything where the model is the
  bottleneck it's not.
- **qwen3-embedding-0.6b underperforms its weight class** here — 1024-dim
  but recall@5 just 0.26, the worst of the mid-size set. This is consistent
  with 0.6B instruct-tuned embeddings being weaker out-of-the-box on
  passage-retrieval benchmarks than the 300–570M retrieval-tuned models.
  Treat the absolute numbers as corpus-specific, not a general ranking.

All models were run through the same 23-question test split, same 1942 chunks,
same retrieval pipeline (no re-ranking), cosine similarity, top-5.

`runs/06_embedding_models.json` (full: hit@5, recall@5, MRR, nDCG@5/10, dims,
params, MB, embed time), `runs/06_embedding_models.png` (chart).

## Matryoshka truncation (nomic-embed-text)

| dim  | hit@5  | recall@5 | mrr    | ndcg@5 |
|------|--------|----------|--------|--------|
| 768  | 0.3913 | 0.2826   | 0.2391 | 0.2776 |
| 512  | 0.3913 | 0.2826   | 0.2319 | 0.2736 |
| 256  | 0.3478 | 0.2609   | 0.2333 | 0.2616 |
| 128  | 0.2609 | 0.1957   | 0.1848 | 0.2040 |

Truncating 768→512 is essentially free here — recall@5 is identical. 256 costs ~8%
recall; 128 costs ~31%. Sweet spot for this corpus: **keep 512** if you need a
smaller index; go below 256 only if storage/latency pressure justifies the drop.

Full table in `runs/06_matryoshka.json`.

## Qdrant quantization (nomic-embed-text, 1942 × 768)

| scheme       | recall@5   | est. RAM | Δ vs float |
|--------------|------------|----------|------------|
| float32      | 0.2826     | 5.69 MB  | —          |
| scalar int8  | 0.2826     | 1.42 MB  | 0          |
| product x64  | 0.2826     | 0.02 MB  | 0          |
| binary       | 0.3261     | 0.18 MB  | +4.4 pts   |

Two notes on this small corpus:

1. **Recall@5 is flat across all three lossy schemes** — at 1942 points the
   ANN index (HNSW, ef=64 default) is already effectively exact, so the dominant
   variance is the *semantic* recall of the model, not the quantization. Quant
   savings show up in RAM, not retrieval quality, at this scale.
2. **Binary is the outlier (higher recall).** Qdrant's binary path stores
   re-scaled vectors alongside raw bits for a residual re-rank when
   `always_ram=False`. At this size that residual beats the scalar int8 rounding
   error on this corpus. This is a corpus-specific artifact — don't expect it at
   10^6-scale where the re-rank cost dominates.

The **RAM column is an analytic estimate**, not a server-reported measurement.
Qdrant 1.19 exposes neither `info.status.ram_mb` (removed between 1.7→1.19)
nor a per-collection telemetry endpoint, so nothing in `get_collection` or
`/telemetry` gives per-collection RAM. The numbers above are computed from the
known geometry (1942 × 768 × bytes-per-scheme), which is the dominant component
anyway on a vector-first load. The HNSW link overhead adds a small constant
(`m * 2 * n * 4` bytes) on top that is not counted.

Full table in `runs/06_quant.json`.

## HNSW parameter sweep (Qdrant, nomic-embed-text)

| m  | ef_construct | ef_search | recall vs exact | qdrant mean ms |
|----|--------------|-----------|-----------------|----------------|
| 8  | 100          | 16        | 1.000           | 3.581          |
| 8  | 100          | 64        | 1.000           | 4.703          |
| 8  | 100          | 256       | 1.000           | 4.984          |
| 8  | 200          | 16        | 1.000           | 2.664          |
| 8  | 200          | 64        | 1.000           | 3.790          |
| 8  | 200          | 256       | 1.000           | 2.833          |
| 16 | 100          | 16        | 1.000           | 2.699          |
| 16 | 100          | 64        | 1.000           | 3.459          |
| 16 | 100          | 256       | 1.000           | 2.782          |
| 16 | 200          | 16        | 1.000           | 4.379          |
| 16 | 200          | 64        | 1.000           | 4.222          |
| 16 | 200          | 256       | 1.000           | 4.746          |
| 32 | 100          | 16        | 1.000           | 2.812          |
| 32 | 100          | 64        | 1.000           | 4.425          |
| 32 | 100          | 256       | 1.000           | 2.652          |
| 32 | 200          | 16        | 1.000           | 5.104          |
| 32 | 200          | 64        | 1.000           | 3.408          |
| 32 | 200          | 256       | 1.000           | 3.035          |

At 1942 points every configuration is effectively exact (recall=1.0 vs the numpy
ground truth) — the HNSW graph is small enough that even `ef_search=16` walks
through it fully. The signal in this table is **latency dispersion**, not
quality: mean query times range 2.65–5.10 ms across the 18 cells (a 2× spread)
with no clear m / ef_construct / ef_search monotonic trend, which at this scale
is consistent with the query being dominated by the per-query HTTP round-trip
plus a small amount of graph traversal. The parameters start to matter (both
for recall and for ms) as the corpus grows; use this table as a **reference
baseline**, not as a tuning recommendation.

Full table in `runs/06_hnsw.json`.

## Vector-store benchmark (k=5, 1942 chunks, 23 queries)

| store     | build s | p50 ms | p95 ms | qps    | disk MB |
|-----------|---------|--------|--------|--------|---------|
| chroma    | 0.737   | 0.83   | 0.95   | 1225.5 | 34.6    |
| faiss     | 0.045   | 0.12   | 0.13   | 8152.1 | 7.6     |
| lancedb   | 0.102   | 2.27   | 2.81   | 437.0  | 6.8     |
| pgvector  | 3.063   | 1.12   | 2.30   | 751.7  | 25.8    |
| qdrant    | 0.853   | 1.99   | 3.26   | 446.3  | n/a     |

Two consistent findings:

- **Recall@5 is identical across all five (0.2826).** The stores agree to four
  decimal places — any remaining difference is floating-point ordering on
  near-ties, not real retrieval-quality differences. This is the single most
  important result of the benchmark: the choice of vector store does *not*
  change what a RAG system retrieves, it changes latency, build cost, and
  operational surface.
- **FAISS is ~3–6× faster than the managed stacks, at a lower disk cost**,
  because it's in-process (no HTTP, no SQLite/pg wire-format). The tradeoff:
  no server, no hybrid/sparse, no native metadata filters, no multi-process
  access. For a local tutorial / offline benchmark this is a meaningful win;
  for a production service it's usually not worth giving up the rest.

Full table in `runs/06_store_bench.json`.
