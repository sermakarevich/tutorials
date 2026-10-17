# 14a quickstart verification report (2026-09-09)

Clean-ish reset: `rm -rf project/.venv project/data/indexes` only.
`project/data/cache` (41,630 entries) and `project/runs` were left untouched.

## Wall-clock timings (Mac, from `project/`)

- `just sync`: ~2 s (rebuilds `.venv` with main + `dev` deps; uv cache warm)
- `just check`: ~3 s — Ollama reachable (0.32.12), chat model `qwen3.8:27b`
  answers, embedding dim 768, corpus 12/12 papers parsed, Qdrant "not started"
  (expected — opt-in via `just up qdrant`)
- `just scoreboard`: ~4 s — wrote `runs/scoreboard.md` (65 rows) plus analysis
  md and chapter-13 plots
- `uv run pytest tests/ -q -m "not slow"`: ~39 s before fix (2 collection
  errors); ~5 s after fix — **146 passed, 4 skipped, 3 deselected**

## Fixes made (one-line list)

- `project/tests/test_08_langchain.py`: added
  `pytest.importorskip("langchain_community")` /
  `pytest.importorskip("langchain_core")` before the framework imports.
- `project/tests/test_09_llamaindex.py`: added
  `pytest.importorskip("llama_index")` before the framework imports.

Root cause: chapters 08/09 keep framework packages in opt-in uv dependency
groups (`uv sync --group langchain`, `--group llamaindex`; see chapters
`08_langchain_langgraph.md`, `09_llamaindex.md`), so a plain `just sync` does
not install them and the two test modules failed at import (collection
errors). Sibling modules already handled this the same way (`test_10` skips
without `haystack`/`dspy`, `test_11` without `lightrag`); test_08/09 were
just missing the guards. No `justfile`/`pyproject.toml` change needed — the
opt-in group design is deliberate (ch.09 documents a chromadb pin conflict
between the LangChain and LlamaIndex groups, so `--all-groups` in `sync`
was deliberately avoided).

## Known issues (deferred, out of scope)

- The 4 skips (`test_08`, `test_09`, `test_10`, `test_11-lightrag`) only RUN
  with their opt-in groups installed (e.g.
  `uv sync --group langchain --group llamaindex --group haystack --group dspy --group lightrag`);
  running the full framework test set with all groups installed was not
  verified here.
- `just check` reports Qdrant as "not started" — expected; vector-store
  chapters start it per-chapter with `just up qdrant`.

## Teardown

- `just down qdrant` run at end (removed the stopped `rag-qdrant` container);
  no other compose profiles were running.
