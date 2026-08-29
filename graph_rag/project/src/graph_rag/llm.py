"""Thin client for the Ollama server: chat, structured chat, and embeddings.

Ollama runs on a remote GPU box reached through an SSH tunnel, so every call
can take 10-60 seconds. We log how long each call took so slow runs are
visible instead of looking like a hang.
"""

import time

import httpx
from pydantic import BaseModel

from graph_rag.config import settings

_EMBED_BATCH_SIZE = 32


def chat(messages: list[dict], **opts) -> str:
    """Send a chat request and return the assistant's reply text."""
    payload = {
        "model": settings.chat_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, **opts},
    }
    start = time.monotonic()
    response = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    elapsed = time.monotonic() - start
    print(f"[llm.chat] {elapsed:.1f}s model={settings.chat_model}")
    return response.json()["message"]["content"]


def chat_json(messages: list[dict], schema: type[BaseModel]) -> BaseModel:
    """Send a chat request constrained to a JSON schema, parsed into `schema`.

    Retries once (re-asking the model) if the first reply is not valid JSON
    for the given schema, since small local models occasionally emit
    malformed output even in JSON mode.
    """
    payload = {
        "model": settings.chat_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema.model_json_schema(),
        "options": {"temperature": 0},
    }
    last_error: Exception | None = None
    for attempt in range(2):
        start = time.monotonic()
        response = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        elapsed = time.monotonic() - start
        content = response.json()["message"]["content"]
        print(f"[llm.chat_json] attempt={attempt + 1} {elapsed:.1f}s model={settings.chat_model}")
        try:
            return schema.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001 - retry once, then re-raise
            last_error = exc
    raise ValueError(f"chat_json failed to parse a valid {schema.__name__}: {last_error}")


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts, batching requests to at most 32 texts each."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        payload = {"model": settings.embed_model, "input": batch}
        start = time.monotonic()
        response = httpx.post(f"{settings.ollama_url}/api/embed", json=payload, timeout=120)
        response.raise_for_status()
        elapsed = time.monotonic() - start
        print(f"[llm.embed] batch={len(batch)} {elapsed:.1f}s model={settings.embed_model}")
        vectors.extend(response.json()["embeddings"])
    return vectors
