# OpenMetadata tutorial — from what it is to running lineage, quality and governance

**What it is.** OpenMetadata (open-metadata.org, built by the company Collate) is an open-source **data catalog**: one server that holds **metadata**, meaning data about your data. That covers table and column names, descriptions, owners, lineage (which table is built from which), statistics and test results. It never copies the data itself.

**What problem it solves.** In a company with many databases, dashboards and pipelines, people cannot answer simple questions: *where is the revenue data? what does this column mean? what breaks if `raw.orders` changes? can I trust this number? who owns it, and is it personal data?* OpenMetadata answers all five (discovery, catalog, lineage, data quality, governance) in one place.

**How it works, in 4 steps.**
1. You register each source system (a database, a BI tool) as a **service**.
2. **Ingestion workflows** (small YAML jobs run by a **connector**) read the metadata from that source and send it to the OpenMetadata server, either once or on a schedule through Airflow.
3. The server stores each asset as a versioned **entity** with a unique dotted name (an **FQN**, e.g. `brightcup_pg.brightcup.raw.orders`) and indexes it for search.
4. People use the web UI, and programs use the REST API, the Python SDK or the MCP server (for AI assistants). They search, read and enrich the catalog: owners, tags, glossary terms, tests, alerts and contracts.

**When to use it.** Use it when more than a handful of people depend on data they did not build, and "ask the person who made it" has stopped working. For one team with one database, a README is usually enough.

**Who this tutorial is for.** An advanced engineer (data, ML or platform) who knows SQL, Docker, Python and REST, has never used a data catalog, and wants to run OpenMetadata for a team. The tutorial goes strictly top down: what it is → which problems it solves → how it looks → only then architecture, ingestion, API, lineage, quality, governance and operations. A single running example is used throughout: **Brightcup**, a small coffee-bean shop. Its finance dashboard reads `analytics.daily_revenue`, and each chapter makes that number more findable, traceable, trustworthy and governed.

Verified on OpenMetadata **2.0.5** (server, ingestion, `openmetadata-ingestion==2.0.5.0`), Elasticsearch 9.3.0, Postgres 17, Python 3.12 via uv, Docker 29.5.3, just 1.53.0 (2026-10-12).

Retrieve chapters with `ai show tutorials/openmetadata/<chapter>`.

Article written from this tutorial: [knowledge/media/2026-10-12-openmetadata/article.md](../../media/2026-10-12-openmetadata/article.md) (shorter, publishable; see its [index.md](../../media/2026-10-12-openmetadata/index.md)).

## Chapters (read in order)
- [00_quick_grasp.md](00_quick_grasp.md) — what OpenMetadata is, the problem and the 4-step flow; the stack up, a bot token, one metadata ingestion, then `raw.orders` found by search, by API and in the UI.
- [01_problems_it_solves.md](01_problems_it_solves.md) — the five jobs (discovery, catalog, lineage, data quality, governance), each one a question about Brightcup answered once; `just bootstrap` run as a black box.
- [02_ui_tour.md](02_ui_tour.md) — the UI with real screenshots: home, Explore/search with facets, the table page and its tabs, lineage view, observability, Govern, Context Center, Settings, versions.
- [03_architecture_and_deployment.md](03_architecture_and_deployment.md) — server, metadata store, search index, ingestion framework + Airflow, UI; entities stored as versioned JSON; request and ingestion flows; deployment options, sizing and our Compose file explained. **(failed review: index-vs-API count claim (nested docs) unproven and hard-coded counts are stale; description-only PATCH not moving the version is unexplained; ES/Postgres/Level terms not glossed at first use; 5.4 GiB total not shown)**
- [04_connectors_and_ingestion.md](04_connectors_and_ingestion.md) — services and connectors, the workflow YAML (source / sourceConfig / sink / workflowConfig), the six workflow types, filter patterns, re-runs and soft deletions, CLI runs vs UI-scheduled pipelines on Airflow, bots. **(failed review: exposes authoring history ("was 8 in the pre-fix draft"); cites numbers no output shows (stage 101); `Processed records` counts not interpreted; usage before/after missing; duplicate Airflow listing)**
- [05_api_and_sdk.ipynb](05_api_and_sdk.ipynb) — entities and FQNs, REST GET/list/paging/`fields`, the search API, JSON Patch, versions and `changeDescription`, soft vs hard delete, the Python SDK. **(failed review: prose claims not backed by output (30 products, Tier2 check, PUT 200); version-history cells and tests depend on one stack's state; shared ingestion-bot contradicts the "one bot per automation" advice; index-path fragility not demonstrated; muddled which version holds which edit)**
- [06_lineage.ipynb](06_lineage.ipynb) — the lineage graph; view, query and manual lineage; column lineage; upstream/downstream depth; impact analysis; a Metabase dashboard node added by API. **(failed review: prose and outputs rely on chapter 08 owners/domain before it is read; cites an unseen "three failures"; an uninterpreted log count; raw ANSI codes in pasted output)**
- [07_data_quality.ipynb](07_data_quality.ipynb) — profiler metrics and sampling; test definitions, cases and suites; pass/fail on the planted defects; custom SQL tests; results over time; incidents. **(failed review: `matchEnum` trap result shown but its mechanism not explained; incident cells depend on earlier runs and do not show the claimed state change)**
- [08_governance.ipynb](08_governance.ipynb) — owners and teams, tiers, classifications and tags (auto PII vs manual), glossary terms on columns, domains and data products, certification. **(failed review: data product skips the existing dashboard (display name passed instead of FQN) and the prose wrongly says none exists; governed-page screenshot not embedded; Manual label attributed to ingestion-bot and extra PII false positives left uninterpreted)**
- [09_access_alerts_contracts_ai.md](09_access_alerts_contracts_ai.md) — users, roles and policies with real 200/403, alerts to a webhook on a test failure, a data contract on `daily_revenue`, the MCP server for AI assistants. **(failed review: the owner-based allow rule is never proven (no ownership-driven 403); unsupported claim on how DataConsumerPolicy reaches the user; too many new things in one step; pasted validate output omits a retry line)**
- [10_wrap_up.md](10_wrap_up.md) — the levels tree filled in, the final real state, a map of the product beyond the tutorial, a production checklist, summary, FAQ, exercises and clean-up. **(failed review: the review job itself failed (reviewer did not submit output), so the chapter is unreviewed)**

## Runnable project
`project/` holds the whole stack and the code: `docker-compose.yml` (the official OpenMetadata 2.0.5 Postgres compose with only names, host ports and volumes changed, plus the Brightcup `shopdb` and a `webhook` receiver), `pyproject.toml` + `uv.lock` (Python 3.12), `shopdb/init/*.sql` and `data/shop/*.csv` (the seed shop with planted defects), `ingestion/*.yaml` (shared and per-chapter workflows), `src/openmetadata_tutorial/` (one module per concern; chapter modules `chNN_*.py`), `tests/`, and a `justfile` (`just` lists every recipe).

```
cd project
just up          # start the stack (first start ~3-5 min, needs ~6 GB RAM for Docker); creates .env from .env.template
just token       # store the ingestion-bot JWT in .env as OM_JWT_TOKEN
just bootstrap   # transform -> metadata -> lineage -> profiler -> classify -> quality (idempotent)
just check       # health, versions, shop row counts
just nb 05_api_and_sdk   # run a chapter notebook in place
just test        # offline tests;  just test-all  adds the ones that need the stack
just down        # stop (keeps data);  just reset  deletes every volume
```

Other recipes: `just ingest <name> [ingest|usage|profile|test|classify]`, `just transform`, `just sql "<query>"`, `just api /v1/...`, `just events`, `just shot <url-path> <out.png>`, `just logs <service>`.

## Local settings
Fixed for every chapter; never changed by a chapter. Passwords are local-only defaults; anything you must supply lives in `project/.env` (copied from `.env.template`, gitignored).

| setting | value |
|---|---|
| OpenMetadata UI and API | http://localhost:**18585** (API under `/api`, e.g. `/api/v1/system/version`); admin port **18586** (`/healthcheck`). Inside Docker: `http://openmetadata-server:8585` |
| UI login (local only) | `admin@open-metadata.org` / `admin` |
| API auth | ingestion-bot JWT in `project/.env` as `OM_JWT_TOKEN`, written by `just token`; helpers fall back to an admin login |
| Airflow (ingestion container) | http://localhost:**18080** (login `admin` / `admin`); inside Docker `http://ingestion:8080` |
| Elasticsearch | http://localhost:**19200**; inside Docker `elasticsearch:9200` |
| OpenMetadata's own database (metadata store) | Postgres on `localhost:`**15432**; db `openmetadata_db`, user `openmetadata_user` / `openmetadata_password` |
| Brightcup shop database | Postgres 17 on `localhost:`**15433**; inside Docker `shopdb:5432`; db `brightcup`; admin `shop_admin` / `shop123`; read-only ingestion user `om_reader` / `reader123`; `pg_stat_statements` enabled |
| database service in OpenMetadata | `brightcup_pg` (tables `brightcup_pg.brightcup.raw.*`, `brightcup_pg.brightcup.analytics.*`) |
| demo user (chapters 08/09) | `dana.analyst@brightcup.example` / `DANA_PASSWORD` in `.env` |
| webhook receiver (alerts) | http://localhost:**18090** (`GET /events`, `DELETE /events`); inside Docker `http://webhook:8000/<any-path>` |
| containers | `om-tutorial-server`, `om-tutorial-migrate` (runs once), `om-tutorial-metadb`, `om-tutorial-search`, `om-tutorial-ingestion`, `om-tutorial-shopdb`, `om-tutorial-webhook` |
| Compose project | `om-tutorial` (named volumes `om-tutorial_*`) |
| images | `docker.getcollate.io/openmetadata/{server,ingestion,postgresql}:2.0.5`, `docker.elastic.co/elasticsearch/elasticsearch:9.3.0`, `postgres:17`, `python:3.12-slim` |
| Python | 3.12 via `uv`; package `openmetadata_tutorial` in `project/src/`; `openmetadata-ingestion[postgres]==2.0.5.0` (client version must equal server version) |
