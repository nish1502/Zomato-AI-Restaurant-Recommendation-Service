from __future__ import annotations

import os

import polars as pl
import pytest

from app.llm.groq_ranker import GroqRanker
from app.schemas.recommendations import RecommendationQuery


@pytest.mark.asyncio
async def test_groq_re_rank_integration():
    """
    Phase 3 integration test against Groq.

    - Requires GROQ_API_KEY to be set in the environment.
    - Uses a tiny synthetic candidate set to keep the prompt small.
    - Verifies that GroqRanker returns a non-empty result and only uses
      candidate IDs we provided.
    """
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping Groq integration test")

    df = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Test A", "Test B", "Test C"],
            "location": ["Test Area", "Test Area", "Test Area"],
            "rating_numeric": [4.5, 4.0, 3.5],
            "votes": [120, 80, 10],
            "cuisines_normalized": [
                ["test", "north indian"],
                ["test", "chinese"],
                ["test"],
            ],
            "approx_cost_for_two": [600, 400, 300],
        }
    )

    query = RecommendationQuery(
        location="Test Area",
        cuisines=["North Indian", "Chinese"],
        min_rating=3.0,
        budget_min=200,
        budget_max=800,
        max_results=3,
    )

    ranker = GroqRanker()
    result = await ranker.re_rank(query, candidates=df, max_candidates=3)
    await ranker.aclose()

    assert result is not None
    assert result.restaurants

    candidate_ids = {1, 2, 3}
    returned_ids = {r.id for r in result.restaurants}
    assert returned_ids.issubset(candidate_ids)

