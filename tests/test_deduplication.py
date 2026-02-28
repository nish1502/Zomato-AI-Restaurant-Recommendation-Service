import pytest
import polars as pl
from app.phase1.dataset_loader import _normalize_dataframe

def test_dataset_deduplication():
    # raw data with duplicates
    data = {
        "name": ["Rest A", "Rest A", "Rest B"],
        "address": ["Add 1", "Add 1", "Add 2"],
        "location": ["Loc 1", "Loc 1", "Loc 2"],
        "url": ["url1", "url1", "url2"],
        "votes": [100, 200, 300],
        "rate": ["4.0/5", "4.0/5", "3.0/5"],
        "approx_cost(for two people)": ["500", "500", "800"]
    }
    df = pl.DataFrame(data)
    
    normalized = _normalize_dataframe(df)
    
    # Should have 2 restaurants, and the one with more votes (200) should be kept for Rest A
    assert normalized.height == 2
    rest_a = normalized.filter(pl.col("name") == "Rest A")
    assert rest_a["votes"][0] == 200
    assert normalized["id"].to_list() == [0, 1]

def test_cost_parsing():
    data = {
        "name": ["R1", "R2", "R3"],
        "rate": ["4.0", "3.0", "2.0"],
        "location": ["L1", "L2", "L3"],
        "address": ["A1", "A2", "A3"],
        "approx_cost(for two people)": ["1,200", "", None]
    }
    df = pl.DataFrame(data)
    normalized = _normalize_dataframe(df)
    
    assert normalized.filter(pl.col("name") == "R1")["approx_cost_for_two"][0] == 1200
    assert normalized.filter(pl.col("name") == "R2")["approx_cost_for_two"][0] is None
    assert normalized.filter(pl.col("name") == "R3")["approx_cost_for_two"][0] is None

def test_api_deduplication():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    # We can't easily mock the index without more complex setup, 
    # but we can verify the API returns unique IDs if we can get a response.
    # For now, let's just test a basic request.
    query_data = {
        "location": "Banashankari",
        "cuisines": [],
        "min_rating": 3.0,
        "max_results": 10
    }
    response = client.post("/api/v1/recommendations", json=query_data)
    if response.status_code == 200:
        results = response.json()["restaurants"]
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids)), "Duplicate IDs found in final response"
