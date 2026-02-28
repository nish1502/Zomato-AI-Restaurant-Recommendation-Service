"""
Thin wrappers re-exporting the canonical Phase 2 recommendation schemas.

Existing imports (`app.schemas.recommendations`) should continue to work,
while the main implementation now lives in `app.phase2.schemas.recommendations`.
"""

from app.phase2.schemas.recommendations import *  # noqa: F401,F403
