"""Replay mode: the demo safety net.

Every LLM call is keyed by sha256(agent, model tier, normalized prompt). With DEMO_REPLAY=1, or
when no Groq key is set, a matching recording in recordings/ is returned instead of calling Groq.
With QUORUM_RECORD=1, live responses are saved as new recordings. Seed demo inputs always ship
with recordings, so the stage demo and the test suite never depend on Groq.

Built in Phase 3 (see PLAN_BACKEND.md).
"""
