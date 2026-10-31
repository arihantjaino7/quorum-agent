"""LangGraph wiring.

normalizer → extractor → memory_retriever → conflict_detector → ripple
  → review (interrupt) ⇄ review_editor → executor → memory_writer

SQLite checkpointer; thread_id = run id. Each node emits AgentEvents through app.services.runs.
Built in Phase 2 (walking skeleton with pass-through stub nodes) and filled in over Phases 4–8.
"""
