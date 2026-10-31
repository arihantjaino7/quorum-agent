"""Recording store. One JSON file per recorded LLM call: recordings/<agent>/<key[:16]>.json.

The key is sha256 of (agent, tier, output schema, whitespace-normalized messages). The model name
is deliberately not part of the key, so switching models keeps recordings usable; it is stored in
the file, and a mismatch is logged so stale recordings are visible.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


def _normalize(messages: list[tuple[str, str]]) -> list[list[str]]:
    return [[role, " ".join(content.split())] for role, content in messages]


def make_key(agent: str, tier: str, schema: type[BaseModel], messages: list[tuple[str, str]]) -> str:
    blob = json.dumps(
        {"agent": agent, "tier": tier, "schema": schema.model_json_schema(), "messages": _normalize(messages)},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _path(agent: str, key: str) -> Path:
    return RECORDINGS_DIR / agent / f"{key[:16]}.json"


def load(agent: str, key: str) -> dict | None:
    p = _path(agent, key)
    if not p.exists():
        return None
    rec = json.loads(p.read_text())
    return rec if rec.get("key") == key else None


def save(agent: str, key: str, *, tier: str, model: str, schema: type[BaseModel],
         messages: list[tuple[str, str]], output: dict, latency_ms: int) -> Path:
    p = _path(agent, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "key": key,
        "agent": agent,
        "tier": tier,
        "model": model,
        "schema": schema.__name__,
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latency_ms": latency_ms,
        "messages": [{"role": r, "content": c} for r, c in messages],
        "output": output,
    }, indent=2, ensure_ascii=False) + "\n")
    return p
