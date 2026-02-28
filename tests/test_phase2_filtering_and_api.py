from __future__ import annotations

import polars as pl
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.recommendations import RecommendationQuery
from app.services.dataset_loader import get_restaurants_index
from app.services.filtering_engine import filter_restaurants
from app.services.ranking_engine import rank_restaurants


def test_filter_and_rank_pipeline_smoke():
    """
    Phase 2 service-level test:
    - Loads the normalized index.
    - Applies filtering for a realistic query.
    - Applies heuristic ranking.
    """
    df = get_restaurants_index(limit=None, force_rebuild=False)
    assert isinstance(df, pl.DataFrame)
    assert df.height > 0

    query = RecommendationQuery(
        location="Banashankari",
        cuisines=["North Indian"],
        min_rating=3.5,
        budget_min=300,
        budget_max=900,
        max_results=10,
    )

    filtered = filter_restaurants(df, query)
    assert filtered.height > 0

    # Verify filters roughly held.
    assert (
        filtered.select(pl.col("rating_numeric").fill_null(0).min()).item()
        >= query.min_rating - 0.01
    )

    ranked = rank_restaurants(filtered, query)
    assert "score" in ranked.columns
    assert ranked.height == filtered.height

    scores = ranked.get_column("score").to_list()
    assert scores == sorted(scores, reverse=True)


def test_recommendations_api_endpoint():
    """
    Phase 2 API-level test using FastAPI TestClient:
    - Calls /api/v1/recommendations with a sample payload.
    - Asserts basic invariants on the response.
    """
    client = TestClient(app)

    payload = {
        "location": "Banashankari",
        "cuisines": ["North Indian", "Chinese"],
        "min_rating": 4.0,
        "budget_min": 300,
        "budget_max": 1000,
        "max_results": 5,
    }

    resp = client.post("/api/v1/recommendations", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["returned"] <= payload["max_results"]

    for r in data["restaurants"]:
        assert r["name"]
        assert r["id"] is not None
        if r["rating"] is not None:
            assert r["rating"] >= payload["min_rating"] - 0.01

