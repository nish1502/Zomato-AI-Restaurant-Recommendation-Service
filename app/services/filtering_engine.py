"""
Thin wrappers re-exporting the canonical Phase 2 filtering engine.

Existing imports (`app.services.filtering_engine`) should continue to work,
while the main implementation now lives in `app.phase2.services.filtering_engine`.
"""

from app.phase2.services.filtering_engine import *  # noqa: F401,F403

