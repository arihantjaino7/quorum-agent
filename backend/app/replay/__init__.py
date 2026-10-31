"""Replay mode: the demo safety net.

Every LLM call made through ``app.integrations.llm.structured`` is keyed by
sha256(agent, tier, output schema, normalized messages); see ``store.py``.

- ``DEMO_REPLAY=1`` (default): a matching recording is returned instantly; on a miss the call goes to
  Groq if it's available, otherwise it fails with a clear, retryable error.
- ``DEMO_REPLAY=0``: recordings are ignored; every call goes to Groq.
- ``QUORUM_RECORD=1``: live answers are saved as recordings (only when asked; never automatic).

Seed demo inputs ship with recordings, so the stage demo and the test suite never depend on Groq.
"""
