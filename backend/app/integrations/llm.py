"""Groq chat models with Pydantic structured output, routed through replay.

    out = await llm.structured("extractor", "strong", ExtractorOut, messages)

- Tiers map to config: "strong" → GROQ_MODEL_STRONG, "fast" → GROQ_MODEL_FAST.
- Strict JSON-schema output, so output schemas must be strict-friendly: every field required, with
  optional values typed as ``X | None`` and no defaults.
- Malformed output or a transient Groq error is retried up to GROQ_MAX_RETRIES times; each retry after
  malformed output tells the model what was wrong. A timeout (GROQ_TIMEOUT_S) fails immediately, so the
  stage never freezes for minutes.
- Rate limits (429): if Groq's suggested wait fits within GROQ_TIMEOUT_S, wait (reported through the
  ``progress`` hook as "waiting for Groq…") and retry; otherwise fail with a clear rate-limit error.
- A fast-tier call that Groq refuses as "request too large" (free-tier output cap) is retried once on
  the strong model.
- Groq availability: GROQ_API_KEY if set, otherwise a one-time probe of the model list (the key may be a
  network secret that the outbound proxy attaches).
"""

import asyncio
import logging
import re
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.replay import store

log = logging.getLogger("quorum.llm")

Tier = Literal["strong", "fast"]
GROQ_BASE = "https://api.groq.com/openai/v1"
PROXY_PLACEHOLDER_KEY = "proxy-injected"  # replaced by the outbound proxy when the key is a network secret


# Set by the graph's instrumented node so long waits show up in the live trace.
progress: ContextVar[Callable[[str], None] | None] = ContextVar("llm_progress", default=None)


def _report(message: str) -> None:
    hook = progress.get()
    if hook is not None:
        hook(message)


class LLMUnavailable(RuntimeError):
    """No recording matches and Groq isn't reachable."""


class LLMFailed(RuntimeError):
    """Groq answered, but not with valid output, after all retries (or it timed out)."""


class RequestTooLarge(LLMFailed):
    """Groq refused the request up front: it exceeds the model's free-tier per-minute output cap."""


# ---------------------------------------------------------------- availability

_available: bool | None = None


def _api_key() -> str:
    return get_settings().groq_api_key or PROXY_PLACEHOLDER_KEY


def probe() -> bool:
    """Decide once whether Groq is usable. Called at startup; cached."""
    global _available
    s = get_settings()
    if s.groq_api_key:
        _available = True
    elif not s.groq_autodetect:
        _available = False
    else:
        try:
            r = httpx.get(f"{GROQ_BASE}/models", headers={"Authorization": f"Bearer {_api_key()}"}, timeout=3)
            _available = r.status_code == 200
        except httpx.HTTPError:
            _available = False
        if _available:
            log.info("[groq] reachable via the network proxy (no GROQ_API_KEY set)")
    if not _available:
        log.warning("[groq] not configured or unreachable; replay recordings only")
    return _available


def available() -> bool:
    return probe() if _available is None else _available


def reset_probe() -> None:
    global _available
    _available = None


def replay_active() -> bool:
    """True when recordings are served (DEMO_REPLAY=1, or Groq unavailable)."""
    return get_settings().demo_replay or not available()


def model_for(tier: Tier) -> str:
    s = get_settings()
    return {"strong": s.groq_model_strong, "fast": s.groq_model_fast}[tier]


def reasoning_for(tier: Tier) -> str | None:
    s = get_settings()
    return ({"strong": s.groq_reasoning_strong, "fast": s.groq_reasoning_fast}[tier]) or None


# ---------------------------------------------------------------- live call


async def _complete(model: str, schema: type[BaseModel], messages: list[tuple[str, str]],
                    reasoning: str | None = None) -> dict:
    """One structured call. Returns {"raw": str, "parsed": BaseModel | None, "error": str | None}."""
    from langchain_groq import ChatGroq

    s = get_settings()
    extra = {"reasoning_effort": reasoning} if reasoning else {}
    chat = ChatGroq(model=model, api_key=_api_key(), timeout=s.groq_timeout_s, max_retries=0, temperature=0, **extra)
    runnable = chat.with_structured_output(schema, method="json_schema", strict=True, include_raw=True)
    out = await asyncio.wait_for(runnable.ainvoke(messages), timeout=s.groq_timeout_s)
    err = out.get("parsing_error")
    return {"raw": getattr(out.get("raw"), "content", "") or "", "parsed": out.get("parsed"),
            "error": str(err) if err else None}


_RETRY_IN = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s")


def rate_limit_wait(e: Exception) -> float | None:
    """Seconds Groq asks us to wait for a 429, or None if it isn't a waitable rate limit."""
    text = str(e)
    if "rate_limit_exceeded" not in text and "Rate limit" not in text:
        return None
    m = _RETRY_IN.search(text)
    if not m:
        return None  # e.g. "Request too large": waiting won't help
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def _is_invalid_json(e: Exception) -> bool:
    return "json_validate_failed" in str(e)


def _is_transient(e: Exception) -> bool:
    status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "status_code", None)
    return status in (429, 500, 502, 503, 504) or isinstance(e, (httpx.ConnectError, httpx.ReadError))


async def _live(agent: str, model: str, schema: type[BaseModel], messages: list[tuple[str, str]],
                reasoning: str | None = None):
    s = get_settings()
    convo = list(messages)
    last = "unknown error"
    for attempt in range(s.groq_max_retries + 1):
        try:
            res = await _complete(model, schema, convo, reasoning)
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            raise LLMFailed(f"{agent}: Groq timed out after {s.groq_timeout_s:.0f}s") from e
        except Exception as e:  # noqa: BLE001
            wait = rate_limit_wait(e)
            if wait is None and "rate_limit_exceeded" in str(e):
                raise RequestTooLarge(f"{agent}: request too large for Groq's free-tier per-minute limit") from e
            if wait is not None:
                if wait > s.groq_timeout_s or attempt == s.groq_max_retries:
                    raise LLMFailed(f"{agent}: Groq rate limit (free tier); try again in {wait:.0f}s") from e
                last = f"rate limited ({wait:.0f}s)"
                _report(f"Waiting for Groq rate limit ({wait:.0f}s)…")
                log.warning("[llm] %s attempt %d: rate limited, waiting %.1fs", agent, attempt + 1, wait)
                await asyncio.sleep(wait + 0.25)
                continue
            if _is_invalid_json(e):  # Groq rejected the model's own JSON: malformed output, so retry with feedback
                last = f"invalid output: {e}"
                log.warning("[llm] %s attempt %d: Groq could not produce valid JSON", agent, attempt + 1)
                convo = list(messages) + [("user", "Your previous answer failed JSON validation or was cut off. "
                                                   "Return complete, compact JSON matching the schema.")]
                continue
            if not _is_transient(e):
                raise LLMFailed(f"{agent}: Groq error: {e}") from e
            last = f"Groq error: {e}"
            log.warning("[llm] %s attempt %d: %s", agent, attempt + 1, last)
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
        parsed, error = res["parsed"], res["error"]
        if parsed is not None and error is None:
            try:
                return schema.model_validate(parsed.model_dump() if isinstance(parsed, BaseModel) else parsed)
            except ValidationError as e:
                error = str(e)
        last = f"invalid output: {error}"
        log.warning("[llm] %s attempt %d: %s", agent, attempt + 1, last)
        convo = list(messages) + [
            ("assistant", res["raw"] or "(empty)"),
            ("user", f"That output was invalid: {error}\nReturn corrected JSON that matches the schema exactly."),
        ]
    raise LLMFailed(f"{agent}: no valid output after {s.groq_max_retries + 1} attempts ({last})")


# ---------------------------------------------------------------- public API


async def structured(agent: str, tier: Tier, schema: type[BaseModel], messages: list[tuple[str, str]]) -> BaseModel:
    s = get_settings()
    model = model_for(tier)
    key = store.make_key(agent, tier, schema, messages)
    only = {a.strip() for a in s.quorum_record_only.split(",") if a.strip()}
    recording = s.quorum_record and (not only or agent in only)

    if s.demo_replay and not recording:
        rec = store.load(agent, key)
        if rec is not None:
            if rec["model"] != model:
                log.info("[replay] %s: recording was made with %s; config now says %s", agent, rec["model"], model)
            return schema.model_validate(rec["output"])

    if not available():
        raise LLMUnavailable(
            f"{agent}: no replay recording for this input and Groq isn't configured "
            "(set GROQ_API_KEY, or add Groq as a network secret)"
        )

    t0 = time.perf_counter()
    try:
        out = await _live(agent, model, schema, messages, reasoning_for(tier))
    except RequestTooLarge:
        backup = model_for("strong")
        if tier != "fast" or backup == model:
            raise
        log.warning("[llm] %s: %s over its free-tier output cap; retrying on %s", agent, model, backup)
        _report("qwen over free-tier limit; using backup model" if "qwen" in model
                else "Fast model over free-tier limit; using backup model")
        model = backup
        out = await _live(agent, model, schema, messages, reasoning_for("strong"))
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if recording:
        path = store.save(agent, key, tier=tier, model=model, schema=schema, messages=messages,
                          output=out.model_dump(mode="json"), latency_ms=latency_ms)
        log.info("[replay] recorded %s → %s", agent, path.name)
    return out
