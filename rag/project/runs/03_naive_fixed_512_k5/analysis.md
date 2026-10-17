# Failure analysis: `03_naive_fixed_512_k5`

27 test questions, `correctness` judged 0 / 0.5 / 1. This file only looks at the **9
questions judged 0** (a wrong answer with no partial credit); the 8 questions judged 0.5
(partially right) are a real but separate story — see the chapter's "What changed on the
scoreboard" section for one of those.

## Classification

| class | description | count | question ids |
|---|---|---:|---|
| (a) retrieval miss | no evidence chunk in the top 5 (`hit@5 = 0`) | 6 | `single_hop_008`, `multi_hop_000`, `multi_hop_002`, `comparative_003`, `global_000`, `global_005` |
| (b) generation/reading failure | evidence *was* retrieved (`hit@5 = 1`) but the answer is still wrong | 3 | `single_hop_006`, `multi_hop_006`, `multi_hop_007` |
| (c) chunk-boundary split | evidence was cut across two chunks so neither alone covers it | 0 | — |
| (d) hallucinated unanswerable | an unanswerable question answered anyway | 0 | — |
| (e) judge error | I disagree with the judge's 0 | 0 | — |

**Why (c) is 0 here.** `retrieval_metrics.chunk_covers_quote` already forgives a quote cut a
few words short at a chunk boundary (the 80%-token-overlap fallback from chapter 02) — 512
tokens with 64 overlap is generous relative to the ~40-token evidence quotes in this golden
set, so a clean boundary split essentially never happens at this chunk size. It would show up
sooner at a much smaller chunk size (chapter 04's size ablation is the place to check).

**Why (d) is 0 here.** All 6 unanswerable test questions scored `abstain = 1.0` — but as
chapter 02 noted, these are the *easy* unanswerable questions (a 2027 paper, a protein-folding
non-sequitur); the model can reject them from general knowledge alone, without needing
retrieval to fail loudly. `unanswerable_005` (a nonexistent appendix section) is the harder
test and is worth re-checking once a smarter retriever (chapter 05+) changes what actually
gets retrieved for a plausible-but-absent question.

**Why (e) is 0 here.** I read all 9 zero-scored answers against their reference answers and
the judge's one-sentence reason; in every case the answer was genuinely missing the reference
fact or explicitly refused to answer, and the judge's reason matched what I saw. No disagreement
to report this run — chapter 13 has more to say about judge reliability in general.

**Multi-hop nuance inside class (a).** Two of the three class (b) examples
(`multi_hop_006`, `multi_hop_007`) actually have `recall@5 = 0.5`: one of the two required
evidence passages *was* retrieved, the other was not. I still counted them as "generation
failure" rather than folding them into (a) because in both cases the model had genuinely
useful partial context and chose to refuse entirely instead of answering the half it could
support — a prompting/generation choice, not a retrieval one. But the root cause is still
that flat top-k dense retrieval, searching with one embedding of the whole question, tends to
pull chunks from whichever one of the two papers is a better semantic match and starves the
other — this is exactly why chapter 05 tries hybrid search and chapter 07 tries query
decomposition (split a multi-hop question into two searches).

## Which later chapter addresses which class

| class | addressed by |
|---|---|
| (a) retrieval miss | chapter 04 (chunking strategies: semantic/markdown-structure chunking so a chunk boundary lines up with an idea, not a token count) and chapter 05 (hybrid search: BM25 catches the literal terms dense embeddings under-weight, e.g. "ITERRETGEN") |
| (b) generation/reading failure | chapter 07 (reranking puts the *most* relevant of the 5 retrieved chunks first instead of leaving it to raw cosine order; the "Lost in the Middle" paper in our own corpus is the direct citation for why this matters) |
| (c) chunk-boundary split | chapter 04's chunk-size ablation and small-to-big (parent-child) retrieval |
| (d) hallucinated unanswerable | chapter 07 (a reranker/threshold can suppress low-relevance results entirely) and chapter 13 (a harder, purpose-built unanswerable test set) |
| (e) judge error | chapter 13 (judge-reliability spot-check against a human rater) |

## Three worked examples

### 1. Retrieval miss — `single_hop_008`

> Q: *"According to the survey, what specific mechanism does the ITERRETGEN model use to
> leverage content required to address an input task as a contextual basis for retrieving
> pertinent knowledge?"*
> Reference: *"It employs a synergistic approach that leverages 'retrieval-enhanced
> generation' alongside 'generation-enhanced retrieval'."*
> Evidence: `[rag_survey]` *"ITERRETGEN [14] employs a synergistic approach that
> leverages "retrieval-enhance..."*

`recall@5 = 0.0`, `hit@5 = 0.0` — none of the 5 retrieved chunks (ids `50b36773a200cb66`,
`d7394dfaca2ca5da`, `87d50286bfb8eda0`, `67e04e23a35a6abf`, `6c08f1032593792f`) covered the
evidence quote. The question names a specific model (ITERRETGEN) buried in one paragraph of
a 21,000-token survey; a single dense query embedding of the whole question competed against
512-token chunks covering many other named methods in the same survey and lost. Answer: *"I
cannot answer this from the provided documents."* — correctly abstaining rather than
hallucinating, but scored 0 because the fact genuinely was retrievable, just not retrieved.

### 2. Generation/reading failure — `single_hop_006`

> Q: *"In the FEVER task analysis, what percentage of cases had the top retrieved document
> from a gold article?"*
> Reference: *"71%"*
> Evidence: `[rag]` *"We find that the top retrieved document is from a gold article in 71%
> of cases"*

`recall@5 = 1.0`, `hit@5 = 1.0` — the exact evidence chunk was retrieved (it is in the top
5). The full answer was nonetheless: *"I cannot answer this from the provided documents."*
This is a pure generation failure: the fact was sitting in the context window and the model
declined to use it — plausibly because the system prompt's abstention instruction made the
model over-cautious on a chunk that also discusses several *other* percentages nearby, and it
picked "refuse" over risking the wrong number. Chapter 07's reranking (moving the single most
relevant chunk to the very front, rather than leaving it wherever cosine similarity happened
to rank it — here it was retrieved but not examined closely enough) and prompt-level fixes are
the natural next things to try; this chapter's prompt is frozen so a fix is deferred, not
applied here.

### 3. Retrieval miss, structural — `global_000`

> Q: *"Which papers in the corpus propose specific methods to improve the retrieval step
> itself, rather than focusing on the generation or evaluation of the final answer?"*
> Reference: cites 5 papers (DPR, ColBERTv2, HyDE, RAPTOR, GraphRAG).
> Evidence: one ~300-character abstract excerpt per cited paper (5 quotes total).

`recall@5 = 0.0` — a single top-5 dense search over 509 chunks essentially cannot cover 5
different papers' abstracts at once; the 5 chunks retrieved landed on other papers'
introductions instead. This is not really a "retrieval bug" so much as flat top-k retrieval
being the wrong tool for a *global* question by construction — you would need either a much
larger k, a query broken into 5 sub-queries (one per candidate paper), or a different
retrieval strategy entirely (e.g. summarizing every paper first, as RAPTOR and GraphRAG — two
papers *in this corpus* — propose). The model's answer, to its credit, named real papers with
real retrieval-improving methods (CRAG, Self-RAG) — just not the 5 the reference wanted —
which is why faithfulness for this answer is still fairly high even though correctness is 0:
it did not fabricate anything, it answered a slightly different question than the one the
gold evidence set was built around.
