"""
Thin wrappers re-exporting the canonical Phase 3 Groq ranker.

Existing imports (`app.llm.groq_ranker`) should continue to work, while
the main implementation now lives in `app.phase3.groq_ranker`.
"""

from app.phase3.groq_ranker import *  # noqa: F401,F403

