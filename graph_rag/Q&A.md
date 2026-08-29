# Graph RAG tutorial — Q&A

Questions and answers collected during Q&A sessions about the Graph RAG tutorial
(`knowledge/tutorials/graph_rag/`). Each entry is `question > answer`.

Session started: 2026-08-29

---

**Q: What is the phenomenon sometimes called "lost in the middle"?** (from `01_concepts.md`)

> "Lost in the middle" is the observation that LLMs (Large Language Models) do not read a long prompt evenly. When the answer to a question sits at the very **beginning** or the very **end** of the context, models find it reliably; when the same fact is buried in the **middle** of a long context, accuracy drops sharply — the model behaves as if it had not seen it. Plotted as "accuracy vs. position of the relevant text", the result is a U-shaped curve.
>
> The name comes from the 2023 paper *"Lost in the Middle: How Language Models Use Long Contexts"* (Liu et al., Stanford / UC Berkeley), which tested models on multi-document question answering and key-value retrieval. It showed that a bigger context window does not mean the model *uses* all of that window well: padding the prompt with irrelevant text made answers worse even when everything technically fit.
>
> Why it matters for RAG: this is the second reason the tutorial gives for retrieving instead of pasting the whole corpus into the prompt. Even if the documents fit in the context window, a short, relevant context beats a long, diluted one. Retrieval acts as a filter — find the handful of chunks that matter, put only those in the prompt — so the important text is never "in the middle" of a lot of noise.
>
> Practical consequences in the tutorial: keep the number of retrieved chunks small and ranked; put the highest-scored evidence first (local search in chapter 08 ranks relationships and chunks before building the context); and for whole-corpus questions, summarise first (community summaries in chapter 09) instead of stuffing every chunk into one prompt. Curiously, the survey PDF itself cites this paper, so `Lost in the Middle: How Language Models Use Long Contexts` also appears as a `Paper` entity in the extracted graph (chapters 07–08).

---

