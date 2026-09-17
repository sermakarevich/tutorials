# Tutorials

Hands-on tutorials with runnable companion projects.

| Tutorial | What you learn | Start here |
|---|---|---|
| [neo4j](neo4j/) | Neo4j graph database basics: data model, Cypher queries, Python driver patterns | [neo4j/index.md](neo4j/index.md) |
| [graph_rag](graph_rag/) | Building a GraphRAG (Graph Retrieval-Augmented Generation) pipeline on Neo4j with local LLMs | [graph_rag/index.md](graph_rag/index.md) |
| [jev](jev/) | Using TypeSafe's Jev judge model from Python: Choice / Score / Noul questions, confidence-gated routing, composite scoring, and a real code review of a repo | [jev/README.md](jev/README.md) |

The Neo4j and GraphRAG tutorials have a `project/` folder with a `docker-compose.yml`, a `justfile`, source code and tests;
see their `00_setup.md` for prerequisites (Docker, [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just)).
The Jev tutorial is a single Jupyter notebook with a `justfile` and `pyproject.toml`; it needs a TypeSafe API key, no Docker.
