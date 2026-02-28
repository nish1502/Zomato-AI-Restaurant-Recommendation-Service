"""
Thin wrappers re-exporting the canonical Phase 1 dataset loader.

Existing imports (`app.services.dataset_loader`) should continue to work,
while the main implementation now lives in `app.phase1.dataset_loader`.
"""

from app.phase1.dataset_loader import *  # noqa: F401,F403


