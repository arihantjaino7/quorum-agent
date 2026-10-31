"""Groq chat models with Pydantic structured output, routed through app.replay so recorded
outputs are served in replay mode. Exposes `structured(tier, schema, messages)`.

Built in Phase 3 (see PLAN_BACKEND.md).
"""
