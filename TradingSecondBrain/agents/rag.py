"""RAG over the Obsidian vault.

- Ingestion walks the vault, chunks markdown notes, and embeds them with Ollama
  (nomic-embed-text by default).
- Retrieval supports both Qdrant and Chroma, selected via settings.vector_backend.
- Embedding is cached on disk (``agents/cache/embed_cache.json``) keyed by a SHA-1
  of the chunk text; a re-run only embeds new or changed notes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import frontmatter
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings


# --------------------------------------------------------------------- chunking

CHUNK_SIZE = 800   # characters
CHUNK_OVERLAP = 120
SKIP_DIRS = {"Agents/Logs", "MarketData", ".obsidian", ".trash", ".smart-connections"}
CACHE_PATH = Path(os.environ.get("EMBED_CACHE_PATH",
                                  Path(__file__).parent / "cache" / "embed_cache.json"))
# Embedding dimension for nomic-embed-text. Override via env if you swap models.
DEFAULT_EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))


@dataclass(slots=True)
class Chunk:
    note_path: str
    chunk_id: str
    text: str
    metadata: dict


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _split(text: str) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= CHUNK_SIZE:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + CHUNK_SIZE])
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return out


def _walk_vault(vault: Path) -> Iterable[Path]:
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault).as_posix()
        if any(rel.startswith(skip) for skip in SKIP_DIRS):
            continue
        yield p


def chunk_vault(vault: Path | None = None) -> list[Chunk]:
    vault = (vault or settings.vault_path).expanduser()
    chunks: list[Chunk] = []
    for path in _walk_vault(vault):
        try:
            post = frontmatter.load(path)
        except Exception as e:
            logger.warning(f"frontmatter parse failed {path}: {e}")
            continue
        rel = path.relative_to(vault).as_posix()
        meta = {"path": rel, **{k: v for k, v in post.metadata.items() if isinstance(v, (str, int, float, bool, list))}}
        for i, piece in enumerate(_split(post.content)):
            chunks.append(
                Chunk(
                    note_path=rel,
                    chunk_id=f"{_hash(rel)}-{i}",
                    text=piece,
                    metadata={**meta, "chunk_index": i},
                )
            )
    logger.info(f"chunked {len(chunks)} pieces from vault")
    return chunks


# ------------------------------------------------------------------- embeddings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def embed(text: str) -> list[float]:
    r = httpx.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["embedding"]


# ---------------------------------------------------------------- embed cache


def _load_cache() -> dict[str, list[float]]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"embed cache unreadable, starting fresh: {e}")
        return {}


def _save_cache(cache: dict[str, list[float]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def embed_batch(texts: list[str], cache: dict[str, list[float]] | None = None) -> list[list[float]]:
    """Embed a batch, reusing cached vectors keyed by SHA-1(text)."""
    cache = cache if cache is not None else {}
    out: list[list[float]] = []
    for t in texts:
        key = _hash(t)
        v = cache.get(key)
        if v is None:
            v = embed(t)
            cache[key] = v
        out.append(v)
    return out


# ---------------------------------------------------------------- vector stores


def _stable_point_id(chunk_id: str) -> int:
    """Deterministic 63-bit int derived from the chunk_id (stable across processes)."""
    return int(hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()[:16], 16)


class _QdrantStore:
    def __init__(self) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection not in existing:
            # Probe embedding dimension only when we actually need to create the
            # collection — avoids an Ollama round-trip on every startup.
            try:
                dim = len(embed("dimension probe"))
            except Exception as e:
                logger.warning(f"embed probe failed; falling back to DEFAULT_EMBED_DIM ({DEFAULT_EMBED_DIM}): {e}")
                dim = DEFAULT_EMBED_DIM
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(id=_stable_point_id(c.chunk_id), vector=v,
                        payload={**c.metadata, "text": c.text, "chunk_id": c.chunk_id})
            for c, v in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def query(self, vector: list[float], k: int = 12) -> list[dict]:
        hits = self.client.search(collection_name=self.collection, query_vector=vector, limit=k)
        return [{"score": h.score, **h.payload} for h in hits]


class _ChromaStore:
    def __init__(self) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        self.collection = self.client.get_or_create_collection(name=settings.qdrant_collection)

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[{**c.metadata, "chunk_id": c.chunk_id} for c in chunks],
        )

    def query(self, vector: list[float], k: int = 12) -> list[dict]:
        r = self.collection.query(query_embeddings=[vector], n_results=k)
        out = []
        for i in range(len(r["ids"][0])):
            out.append({
                "score": 1.0 - (r["distances"][0][i] if r.get("distances") else 0.0),
                "text": r["documents"][0][i],
                **(r["metadatas"][0][i] or {}),
            })
        return out


def _store():
    return _QdrantStore() if settings.vector_backend == "qdrant" else _ChromaStore()


# ------------------------------------------------------------------- public API


def ingest(vault: Path | None = None) -> int:
    chunks = chunk_vault(vault)
    if not chunks:
        return 0
    store = _store()
    cache = _load_cache()
    BATCH = 32
    new_or_changed = 0
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        before = sum(1 for c in batch if _hash(c.text) in cache)
        vectors = embed_batch([c.text for c in batch], cache=cache)
        new_or_changed += len(batch) - before
        store.upsert(batch, vectors)
    _save_cache(cache)
    logger.info(
        f"ingested {len(chunks)} chunks into {settings.vector_backend} "
        f"({new_or_changed} re-embedded, {len(chunks) - new_or_changed} cache hits)"
    )
    return len(chunks)


def retrieve(query: str, k: int = 12) -> list[dict]:
    store = _store()
    vec = embed(query)
    hits = store.query(vec, k=k)
    return hits


def cite(hits: list[dict]) -> str:
    """Format retrieval hits as a citations block agents can paste verbatim."""
    lines = []
    for h in hits:
        path = h.get("path", "?")
        score = h.get("score", 0.0)
        snippet = h.get("text", "")[:240].replace("\n", " ")
        lines.append(f"- [[{path}]] (score={score:.3f}) — {snippet}...")
    return "\n".join(lines)


if __name__ == "__main__":  # python -m agents.rag ingest
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    if cmd == "ingest":
        n = ingest()
        print(json.dumps({"ingested": n}))
    elif cmd == "query":
        q = " ".join(sys.argv[2:]) or "current macro regime"
        for h in retrieve(q):
            print(json.dumps(h, default=str))
