# Chapter 12 findings (code + experiments task — handoff to writeup task)

- Bullet points only, no prose polish. Numbers are real runs on the test split (27 questions).

## Scoreboard rows produced (test split, n=27)

| experiment | hit@5 | recall@5 | MRR | nDCG@10 | correctness | faithfulness | unanswerable-abstain | LLM calls/q | s/q |
|---|---|---|---|---|---|---|---|---|---|
| 12_openwebui_default | 0.217 | 0.174 | 0.097 | 0.126 | 0.500 | 0.825 | 1.000 | 1.0 | 19.1 |
| 12_openwebui_hybrid_rerank | 0.261 | 0.196 | 0.172 | 0.196 | 0.587 | 0.872 | 1.000 | 1.0 | 19.8 |

- Hybrid + rerank beats default on EVERY metric (MRR 0.097 -> 0.172 is the biggest jump).
- Retrieval metrics are modest (naive in-house pipelines score higher) partly because the app's
  source chunks are mapped back to our leaf ids via overlap (mapping quality was strong:
  top1_score ~1.4, n_strong_in_top10 ~10 on smoke checks) — writer: do not over-claim, mapping is lossy.
- llm_calls_per_q = 1 by construction (app internals not observable through the API).
- Runs dirs: `runs/12_openwebui_default/`, `runs/12_openwebui_hybrid_rerank/` (metrics.json,
  predictions.jsonl, config.json incl. retrieval_settings + collection_id, mapping.json).
- Config is GLOBAL in Open WebUI (not per-collection): default KB evaluated first under default
  config, then config switched to hybrid_rerank before creating/evaluating the second KB.
- KB ids: default=b926d4c7-ee86-4b15-ae3e-910ca499deb8,
  hybrid_rerank=211addcf-1db4-43d0-8249-d6b3586f1d55.

## Ran vs skipped

- RAN: 12_openwebui_default, 12_openwebui_hybrid_rerank (full 27-q evals, ~16 min each).
- SKIPPED: 12_kotaemon_default, 12_kotaemon_rerank — Gradio API unusable (see below),
  Playwright fallback not attempted (no playwright installed; 27-q UI eval exceeds budget).
- SKIPPED: 12_ragflow_default, 12_ragflow_tuned — time-boxed out (see below).

## Open WebUI live-API discoveries (image ghcr.io/open-webui/open-webui:main, 2026-09-09)

- Retrieval-config push works: POST /api/v1/retrieval/config/update accepts SCREAMING_SNAKE_CASE
  keys (TOP_K, ENABLE_RAG_HYBRID_SEARCH, RAG_RERANKING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
  RAG_EMBEDDING_ENGINE=ollama, RAG_EMBEDDING_MODEL=nomic-embed-text). Verified by 200 + evals.
- /openapi.json and /docs/openapi.json serve the SPA index.html (not JSON) on this build —
  `setup --verify` degrades to a message instead of crashing.
- Knowledge list is GET /api/v1/knowledge/ (trailing slash; /knowledge/list is 404).
- POST /api/v1/knowledge/create works despite GET /knowledge/create 404 (POST-only route).
- File upload returns top-level {"id","filename","data":{"status":...},"meta":{...}} — parser fixed
  to prefer top-level id.
- POST /knowledge/{id}/file/add with {"file_id"} returns 400 while file status is "pending";
  must poll GET /api/v1/files/{id} until data.status == "completed", then retry (implemented).
- Chat sources shape: top-level "sources": [{"source": {...}, "document": [chunk_text, ...]}]
  (document is a LIST of strings); answers carry inline [1]-style citations. Fixture saved:
  tests/fixtures/openwebui_chat_live.json.
- Chat model qwen3.8:27b resolves in /api/chat/completions (Open WebUI model list also shows
  cyber-qwen38-27b:latest from the same Ollama).
- Reranker value used: "cross-encoder/ms-marco-MiniLM-L-6-v2" (accepted by config push; whether the
  server actually downloaded/ran it vs silently ignoring is UNVERIFIED — writer: hedge this).
- Must export .env manually (`set -a; . ./.env; set +a`); `uv run` does not load it.

## kotaemon live-probe result (image ghcr.io/cinnamon/kotaemon:main-lite, port 7870, 2026-09-09)

- 368 named Gradio endpoints; NO stateless chat/upload endpoint exists.
- /chat_fn takes NO message argument (chat_history + UI dropdown state only).
- Message enters via /submit_msg(chat_input, chat_history, conv_name, first_selector_choices).
- Probe 1 (first_selector_choices=None): server TypeError 'NoneType' object is not iterable
  (ktem/pages/chat/__init__.py:903 in submit_msg).
- Probe 2 (choices=[]): sqlalchemy NoResultFound — conv_name must exist in the app's server-side
  SQL session DB; /new_conv creates it inside browser session state, invisible to API clients.
- Conclusion: scripted eval needs UI session replication -> Playwright fallback stands, not done.
- Container stopped at end of task per scope (`just down kotaemon`); restart with
  `just up kotaemon` for the Playwright follow-up.

## RAGFlow time-box (~20 min spent, well under 2 h — STOPPED, not run)

- v0.27.1 manifest is a single image (no multi-arch index) — x86-only confirmed structurally.
- No -slim tag for v0.27.x (slim stops at v0.21.1, verified earlier) — only the ~9 GB full image.
- This Mac: ~300 MB free pages at check time, Docker budget shared with other tutorials' containers,
  documented minimum >= 16 GB RAM (Elasticsearch-backed).
- Decision: no 9 GB pull, no emulation run. Survey entry kept from the research note.
- scripts/ragflow_up.sh / ragflow_down.sh exist (clone pinned tag, UI 8085 / API 9385).

## Survey hands-on (raw notes)

- txtai (NeuML, Apache-2.0, library not app): INSTALLED live via `uv run --with txtai`
  (imports fine, no __version__ attr). Indexed 3 corpus papers with all-MiniLM-L6-v2 (~90 MB
  download) and ran semantic search in 22 s total. First-30-min feel: fastest path of all —
  pip install + 10 lines, zero infra, but you author the RAG app yourself (no UI, no chat API).
- AnythingLLM (Mintplex, MIT): manifest inspect shows linux/amd64 + linux/arm64 (native Mac
  support, unlike RAGFlow). NOT pulled/run (image is GBs; budget). Docs position: desktop-style
  private-ChatGPT with workspaces; Ollama via in-UI provider picker.
- R2R, Onyx, PrivateGPT, Quivr, Khoj: from research note only (all active, thinner verified
  Ollama/API docs) — writer: present as one-line-each table rows, not evaluated.
- Verba (Weaviate): ARCHIVED 2026-06-08, discontinued — one line, excluded.
- Cognita (TrueFoundry): ARCHIVED 2026-03-13, read-only — one line, excluded.

## Library/install issues

- playwright NOT installed (ModuleNotFoundError) — would need `uv add playwright` + browser
  download; skipped as exceeding budget. This blocks the kotaemon fallback.
- gradio_client present in deps (>=2.6.1) and works (view_api + probes all executed).
- txtai installed ephemerally via `uv run --with` (NOT added to pyproject — survey-only).

## Interesting observations (for the writer)

- Open WebUI's reranker+hybrid config won on faithfulness (0.872) as well as retrieval — the
  reranked context is not just better ranked but cleaner to generate from.
- Both app rows abstained perfectly on unanswerables (1.0) — the chat template's citation
  instruction seems to make the model cautious.
- The hardest part of "deploy an app" was not RAG tuning but API shape drift (4 live fixes) —
  a good "apps move fast, verify against the running instance" lesson.
- kotaemon is the only surveyed app with official arm64 images, yet the only one with NO
  scriptable API — native-arch packaging and automation-friendliness are uncorrelated.
- RAGFlow's cost is visible before running anything: 9 GB image + 16 GB RAM vs Open WebUI's
  single 6.5 GB container that ran fine.

## Test state

- `uv run pytest tests/ -q -m "not slow"`: 160 passed, 3 deselected (was 158 + 22 ch12-only).
- tests/test_12_apps.py: 24 tests (parsers on saved fixtures incl. live shapes, settings builders,
  chunk mapping, CLI --help smoke). No network.
