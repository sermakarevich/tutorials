# Tutorials

Hands-on tutorials with runnable companion projects.

| Tutorial | What you learn | Start here |
|---|---|---|
| [neo4j](neo4j/) | Neo4j graph database basics: data model, Cypher queries, Python driver patterns | [neo4j/index.md](neo4j/index.md) |
| [graph_rag](graph_rag/) | Building a GraphRAG (Graph Retrieval-Augmented Generation) pipeline on Neo4j with local LLMs | [graph_rag/index.md](graph_rag/index.md) |
| [jev](jev/) | Using TypeSafe's Jev judge model from Python: Choice / Score / Noul questions, confidence-gated routing, composite scoring, and a real code review of a repo | [jev/README.md](jev/README.md) |
| [openmetadata](openmetadata/) | OpenMetadata data catalog: discovery, lineage, data quality and governance on a coffee-shop example, with Docker Compose stack, ingestion workflows, REST API/SDK and notebooks | [openmetadata/index.md](openmetadata/index.md) |
| [rag](rag/) | Retrieval-Augmented Generation end to end on one corpus (12 arXiv papers, 36-question golden set) and one scoreboard: parsing, chunking, hybrid search, embeddings and vector stores, reranking and query rewriting, LangChain/LangGraph, LlamaIndex, Haystack, DSPy, LightRAG and RAPTOR, Open WebUI and other apps, RAGAS and a local judge, long-context vs RAG, prompt injection, production checklist | [rag/index.md](rag/index.md) |

The Neo4j and GraphRAG tutorials have a `project/` folder with a `docker-compose.yml`, a `justfile`, source code and tests;
see their `00_setup.md` for prerequisites (Docker, [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just)).
The Jev tutorial is a single Jupyter notebook with a `justfile` and `pyproject.toml`; it needs a TypeSafe API key, no Docker.
The RAG tutorial's `project/` has the same shape (compose file, `justfile`, source, tests) plus the committed results of 65 scored runs in `project/runs/`, so `just scoreboard` works without any model; re-running experiments needs a local Ollama with a 27B chat model and a 768-d embedder (see `rag/00_setup.md`), and `just corpus` downloads the papers, which are not committed.
