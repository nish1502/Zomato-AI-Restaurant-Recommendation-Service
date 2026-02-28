"""
Thin wrappers re-exporting the canonical Phase 2 ranking engine.

Existing imports (`app.services.ranking_engine`) should continue to work,
while the main implementation now lives in `app.phase2.services.ranking_engine`.
"""

from app.phase2.services.ranking_engine import *  # noqa: F401,F403

