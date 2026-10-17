# Chapter 10 findings (code + experiments only; handoff to the writeup task)

## What ran (test split, 27 questions; dev split, 9 questions)
- `10_hs_hybrid` (Haystack BM25 + embedding -> RRF joiner, no rerank): ran, full test eval.
- `10_hs_hybrid_rerank` (same + bge-reranker-v2-m3 cross-encoder rerank): ran, full test eval.
- `hs-eval` (Haystack FaithfulnessEvaluator + ContextRelevanceEvaluator with local
  OllamaChatGenerator; DocumentMRREvaluator + DocumentRecallEvaluator): ran on all 27
  `10_hs_hybrid_rerank` predictions; LLM evaluators scored, doc evaluators errored (see below).
- `dump-pipeline` (YAML serialise + reload round-trip, hand-drawn mermaid from `to_dict()`):
  ran; YAML saved at `runs/10_hs_hybrid_rerank/pipeline.yaml`.
- `10_dspy_zero_shot` (RAG module, ch07 best retriever as plain Python, no optimisation): ran.
- `10_dspy_bootstrap` (BootstrapFewShot on dev, max 4+4 demos): ran, then test eval.
- `10_dspy_mipro` (MIPROv2 auto=light on dev, max 2+2 demos): ran, then test eval.
- Skipped: `dspy.Refine`/citation assertions (budget; shared prompt already demands
  `[short_name]` citations). Skipped: Qdrant-backed Haystack store (Qdrant container down;
  InMemory store used). Skipped: trying Ollama's `.../v1` OpenAI-style endpoint for
  evaluators — not needed, both LLM evaluators accepted `OllamaChatGenerator` directly.

## Scoreboard rows (test, k=5; anchors for comparison: ch07 best correctness 0.674)

| row | hit@5 | recall@5 | mrr | ndcg@10 | correctness | faithfulness | s/q |
|---|---|---|---|---|---|---|---|
| 10_dspy_zero_shot | 0.739 | 0.558 | 0.667 | 0.680 | 0.739 | 0.865 | 10.5 |
| 10_dspy_bootstrap | 0.739 | 0.558 | 0.667 | 0.680 | 0.717 | 0.896 | 13.3 |
| 10_dspy_mipro | 0.739 | 0.558 | 0.667 | 0.680 | 0.696 | 0.945 | 11.8 |
| 10_hs_hybrid | 0.609 | 0.471 | 0.373 | 0.431 | 0.696 | 0.702 | 11.5 |
| 10_hs_hybrid_rerank | 0.696 | 0.528 | 0.581 | 0.608 | 0.565 | 0.922 | 10.0 |

- All three DSPy rows share one retriever, so retrieval columns are identical by construction.
- New overall best correctness: `10_dspy_zero_shot` 0.739 (beats ch07 best 0.674).
- Haystack rerank improves retrieval (hit@5 0.609 -> 0.696, mrr 0.373 -> 0.581) but
  correctness DROPS (0.696 -> 0.565) while faithfulness rises (0.702 -> 0.922):
  reranked context is more faithful but the generator answers more conservatively.

## Haystack evaluator agreement (n=27, threshold 0.5; raw rows in `runs/10_hs_evaluators/hs_eval.json`)
- hs FaithfulnessEvaluator: 25/27 scored, mean 0.992; agreement vs our faithfulness: 1.000
  (both judges say "faithful" almost everywhere — ceiling effect, not deep agreement).
- hs ContextRelevanceEvaluator: 26/27 scored, mean 0.769; agreement vs our correctness: 0.783.
- DocumentMRREvaluator + DocumentRecallEvaluator: 0/27 scored — both raise
  `ValueError: The length of ground_truth_documents and retrieved_documents must be the same`
  (gold evidence quotes != retrieved chunk count; needs equal-length lists).
- No evaluator required an OpenAI-style API: both LLM evaluators run fully local on
  `OllamaChatGenerator(model=qwen3.8:27b)`.

## DSPy optimisation details
- LM: `dspy.LM("ollama_chat/qwen3.8:27b", api_base=<ollama_url>, temperature=0,
  max_tokens=4096, num_ctx=16384, think=False, cache=True)`.
  - max_tokens 4096 (not 384/1024): ChainOfThought emits long `reasoning` before `answer`
    from one budget; smaller budgets truncate the answer (AdapterParseError).
  - num_ctx 16384: 5 parent chunks + CoT instructions exceed Ollama's default 4k window.
  - think=False: qwen3.8:27b reasoning fills `reasoning_content`, leaving DSPy an empty
    response otherwise (same reason `rag_tutorial.llm` sends think=False).
- Optimiser metric: cheap token-F1 vs reference (NOT the LLM judge — judge needs ~3 LLM
  calls/example and would blow the <=400-call budget). Final test scoring uses real judges.
- Dev split: 9 examples (small on purpose; overfitting risk is real — see below).
- Bootstrap: 4 LM calls (re-run; teacher traces served from DSPy disk cache; cold cost
  est. ~10-20 calls), 4 demos saved.
- MIPROv2 light: 90 LM calls, 766 s, dev token-F1 39.45; 2 demos saved.
- Optimisation correctness trend on TEST: 0.739 (zero-shot) -> 0.717 (bootstrap) ->
  0.696 (mipro): optimising token-F1 on 9 dev examples overfits and HURTS judge
  correctness; faithfulness rises monotonically 0.865 -> 0.896 -> 0.945.
- MIPRO learned instruction (excerpt, full in `data/cache/dspy/10_dspy_mipro.json`):
  "You are an expert AI assistant specialized in Natural Language Processing (NLP) and
  Large Language Model (LLM) research. Your task is to answer specific technical
  questions based strictly on the provided Context..." (4-step analyze/locate/formulate/format).
- Programs saved: `data/cache/dspy/{10_dspy_zero_shot,10_dspy_bootstrap,10_dspy_mipro}.json`;
  optimiser summary: `runs/10_dspy_optimize_summary.json`.

## Install / API failures and workarounds
- `sentence-transformers-haystack` NOT installed: needs `sentence-transformers>=5.4.0`,
  pinned to `==5.3.0` by `pylate`. Rerank is a custom `@component`
  (`CrossEncoderRankerComponent`) wrapping our `CrossEncoderReranker`
  (`BAAI/bge-reranker-v2-m3`) — same model as specced.
- `haystack-ai==3.1.1` has no `SentenceTransformersSimilarityRanker`
  (`haystack.components.rankers` ships only LLMRanker/LostInTheMiddle/MetaField/...).
- `DocumentSplitter` records NO char start/end offsets — only word-index
  `meta["split_idx_start"]` (+`split_id`, `source_id`); chunk ids remapped as
  `chunk_id(paper, split_idx_start, split_idx_start + len(content))`.
- MIPROv2 needs optional `optuna`: added to the `dspy` group (`optuna==5.0.0`).
- Import-order landmine: `import dspy` BEFORE chromadb/numpy breaks numpy
  (`TypeError: data type 'bool' not understood`); `fw_dspy.py` keeps `import dspy`
  after the `rag_tutorial` imports (comment in file). `python -m` entry points safe.
- `ollama-haystack==6.8.0` embedders/generators call Ollama directly and bypass the
  `rag_tutorial.llm` disk cache: Haystack-side embedding+generation calls are NOT cached
  (judge calls still are). DSPy `cache=True` is a separate on-disk LiteLLM cache.
- `pipeline.draw()` needs network; mermaid drawn by hand from `to_dict()` (in
  `dump-pipeline` output + writeup can regenerate via `draw_mermaid(pipe)`).

## Interesting observations (for the chapter writer)
- DSPy zero-shot with our ch07 retriever is the new correctness SOTA (0.739) with no
  optimisation at all — the retriever does the heavy lifting, CoT just verbalises it.
- Optimising a cheap proxy (token-F1) on 9 dev examples trades correctness for
  faithfulness: a textbook overfitting/proxy-misalignment demo in one table.
- Haystack rerank shows the same trade in retrieval form: better rank metrics, worse
  answers, higher faithfulness — rank quality != answer quality on this set.
- Haystack LLM evaluators work fully local on Ollama (no OpenAI key fiction needed),
  but their faithfulness scores saturate at ~1.0 while ours spread out — lenient judge.
- Haystack's serialised YAML round-trips (reload == same components) but custom
  components need `Pipeline.loads(..., unsafe=True)` — worth one caution box.
