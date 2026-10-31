"""Local embeddings (fastembed) for memory search, stored as float32 blobs in SQLite.

The model loads lazily on first use and is cached on disk (EMBEDDING_CACHE). If it can't load (offline,
no cache), ``embed`` returns None after logging one line, and memory search degrades to topic_key matching.
"""

import logging

import numpy as np
from sqlmodel import Session

from app.config import get_settings
from app.models import Embedding

log = logging.getLogger("quorum.embeddings")

_model = None
_failed = False


def _load():
    global _model, _failed
    if _model is not None or _failed:
        return _model
    s = get_settings()
    if not s.embeddings_enabled:
        _failed = True
        return None
    try:
        from fastembed import TextEmbedding

        try:  # a warm cache must never wait on the network (it can hang for minutes behind a proxy)
            _model = TextEmbedding(s.embedding_model, cache_dir=s.embedding_cache, local_files_only=True)
        except Exception:  # noqa: BLE001 - first run: download once
            _model = TextEmbedding(s.embedding_model, cache_dir=s.embedding_cache)
    except Exception as e:  # noqa: BLE001
        _failed = True
        log.warning("[embeddings] model unavailable (%s); memory search falls back to topic matching", e)
    return _model


def available() -> bool:
    return _load() is not None


def embed(texts: list[str]) -> np.ndarray | None:
    """Unit-normalized vectors, shape (n, dims), or None when embeddings are unavailable."""
    model = _load()
    if model is None or not texts:
        return None
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.where(norms == 0, 1, norms)


def decision_text(topic_key: str, statement: str) -> str:
    return f"{topic_key.replace('_', ' ')}: {statement}"


def vectors_for(session: Session, items: dict[str, str]) -> dict[str, np.ndarray]:
    """Vectors for {item_id: text}, computing and storing any that are missing. Empty if unavailable."""
    out: dict[str, np.ndarray] = {}
    missing: list[str] = []
    model_name = get_settings().embedding_model
    for item_id in items:
        row = session.get(Embedding, item_id)
        if row is not None and row.model == model_name:
            out[item_id] = np.frombuffer(row.vector, dtype=np.float32)
        else:
            missing.append(item_id)
    if missing:
        vecs = embed([items[i] for i in missing])
        if vecs is None:
            return {}
        for item_id, v in zip(missing, vecs):
            row = session.get(Embedding, item_id) or Embedding(item_id=item_id, model=model_name, vector=b"")
            row.model, row.vector = model_name, v.tobytes()
            session.add(row)
            out[item_id] = v
        session.commit()
    return out


def reset_cache_for_tests() -> None:
    global _model, _failed
    _model, _failed = None, False
