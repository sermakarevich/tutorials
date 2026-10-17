# Chapter 09 findings — LlamaIndex (code + experiments)

- Env: project venv python 3.14, llama-index-core 0.14.24, llama-index-llms-ollama 0.11.0,
  llama-index-embeddings-ollama 0.10.0, llama-index-vector-stores-qdrant 0.10.3 (qdrant-client 1.19.0),
  llama-index-retrievers-bm25 0.8.0, llama-index-postprocessor-sbert-rerank 0.6.0,
  sentence-transformers 5.3.0, bm25s 0.3.11, ollama 0.6.2.
- LLM/embeddings: Ollama qwen 27b (Metal, sequential, temp 0.0) + Ollama embeddings; reranker bge-reranker-v2-m3 (local, downloaded fine).
- All spec packages installed OK; nothing failed to install, no substitutions.

## Experiments: ran vs skipped

- Ran 27/27 questions on all 10 pipelines: 09_li_naive, 09_li_sentence_window, 09_li_auto_merging,
  09_li_fusion, 09_li_fusion_rerank, 09_li_subquestion, 09_li_router,
  09_li_mode_compact, 09_li_mode_refine, 09_li_mode_tree_summarize.
- Ran li-eval (built-in evaluators on 09_li_fusion_rerank predictions): 27/27 rows, 0 errors.
- Skipped: RAPTOR pack — `llama-index-packs-raptor` is deprecated per research note; chapter 11 builds RAPTOR by hand.
- Skipped: LlamaCloud/LlamaParse (hosted) — per spec, local-only.
- Router caveat: global_005 hit SummaryIndex tree_summarize runaway (ReadTimeout after 954.7s at 900s timeout);
  recorded as error row, eval continued; metrics below are over 27 rows incl. that error row.

## Results (test split, n=27; cols: hit@5 recall@5 MRR nDCG@10 correctness faithfulness abstain LLMcalls/q s/q)

| experiment | hit@5 | recall@5 | MRR | nDCG@10 | correctness | faithfulness | abstain | calls/q | s/q |
|---|---|---|---|---|---|---|---|---|---|
| 09_li_naive | 0.391 | 0.304 | 0.304 | 0.329 | 0.391 | 0.965 | 1.000 | 1.000 | 0.277 |
| 09_li_sentence_window | 0.435 | 0.348 | 0.351 | 0.371 | 0.413 | 0.957 | 1.000 | 1.000 | 0.665 |
| 09_li_auto_merging | 0.348 | 0.283 | 0.221 | 0.255 | 0.304 | 0.953 | 1.000 | 1.000 | 2.120 |
| 09_li_fusion | 0.609 | 0.484 | 0.504 | 0.527 | 0.543 | 0.964 | 1.000 | 3.000 | 34.884 |
| 09_li_fusion_rerank | 0.739 | 0.608 | 0.588 | 0.619 | 0.652 | 0.951 | 1.000 | 3.000 | 56.962 |
| 09_li_subquestion | 0.304 | 0.239 | 0.097 | 0.148 | 0.739 | 0.919 | 1.000 | 5.185 | 450.074 |
| 09_li_router | 0.391 | 0.304 | 0.304 | 0.329 | 0.478 | 0.871 | 1.000 | 1.926 | 165.326 |
| 09_li_mode_compact | 0.391 | 0.304 | 0.304 | 0.329 | 0.500 | 0.908 | 1.000 | 1.000 | 94.704 |
| 09_li_mode_refine | 0.391 | 0.304 | 0.304 | 0.329 | 0.457 | 0.892 | 1.000 | 5.000 | 375.293 |
| 09_li_mode_tree_summarize | 0.391 | 0.304 | 0.304 | 0.329 | 0.522 | 0.911 | 1.000 | 1.000 | 110.324 |

## Built-in evaluators vs our judge (on 09_li_fusion_rerank, n=27)

| comparison | agreement |
|---|---|
| LI FaithfulnessEvaluator passing vs ours faithfulness>=0.5 | 0.593 (16/27) |
| LI CorrectnessEvaluator passing vs ours correctness>=0.5 | 0.739 |
| LI RelevancyEvaluator passing vs ours correctness>=0.5 | 0.696 |
- LI raw pass counts: faithfulness 16/27 True, relevancy 22/27 True, correctness 15/27 True.
- Full per-question rows: `runs/09_li_evaluators/li_eval.json`.

## Bugs hit during this task (fixed in `fw_llamaindex.py`)

- `CountingOllama.calls: int = 0` on a pydantic-model subclass is a model field, not a class
  attribute: first `type(self).calls` read in a fresh process raises `AttributeError: calls`.
  Fixed with `calls: ClassVar[int] = 0`. (Eval pipelines never saw it because they reset the counter first.)
- LI sync `.evaluate()` wrapper (`asyncio_run`) fails on the 2nd+ call in the same process on
  Python 3.14 (bogus "Detected nested async" on every call after the first). `li-eval` now drives
  async `aevaluate` directly under a single `asyncio.run`, sequential, with per-question
  try/except + incremental `li_eval.jsonl` resume.

## Interesting observations (for chapter writer)

- Fusion+rerank is the retrieval winner (hit@5 0.739 vs naive 0.391), yet subquestion — the worst
  retriever on chunk-id metrics (hit@5 0.304) — has the best answer correctness (0.739): decomposition
  answers well even when retrieved chunk ids don't match gold (metric undercounts synthesis).
- `refine` response mode costs 5x the LLM calls (5.0/q, 375s/q) and scores WORSE (0.457) than `compact`
  (0.500, 1 call) and `tree_summarize` (0.522): more passes != better answers on this set.
- Auto-merging is the only pipeline worse than naive on retrieval (0.348 vs 0.391): hierarchical
  merge assumptions don't fit this markdown corpus.
- Router pays 165s/q and a 954s timeout blowup on one global question for +0.087 correctness over naive;
  its retrieval equals naive (routes mostly to the vector engine; summary answers don't map to chunk ids).
- Faithfulness is uniformly high (0.87-0.96) across all 10 pipelines — generator is grounded; correctness
  spread (0.304-0.739) comes from retrieval/decomposition, not hallucination.
