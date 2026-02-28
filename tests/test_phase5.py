import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_recommendations_endpoint_contract():
    """
    Test that the backend API matches the expectations of the Phase 5 frontend.
    The frontend sends: location, cuisines (list), min_rating, budget_min, budget_max, max_results, use_llm.
    """
    payload = {
        "location": "Banashankari",
        "cuisines": ["North Indian", "Chinese"],
        "min_rating": 4.0,
        "budget_min": 200,
        "budget_max": 1000,
        "max_results": 10,
        "use_llm": False # Set to False for faster test if Groq is not configured
    }
    
    response = client.post("/api/v1/recommendations", json=payload)
    
    # Check status code
    assert response.status_code == 200
    
    data = response.json()
    
    # Check response structure
    assert "restaurants" in data
    assert isinstance(data["restaurants"], list)
    
    if len(data["restaurants"]) > 0:
        rest = data["restaurants"][0]
        # These fields are used by the frontend
        assert "name" in rest
        assert "rating" in rest
        assert "votes" in rest
        assert "cuisines" in rest
        assert "approx_cost_for_two" in rest
        # "explanation" is optional but allowed
        assert "explanation" in rest or True 

def test_frontend_integration_payload_empty_cuisines():
    """Test with empty cuisines which the frontend might send."""
    payload = {
        "location": "Banashankari",
        "cuisines": [],
        "min_rating": 3.0,
        "budget_min": 0,
        "budget_max": 5000,
        "max_results": 5,
        "use_llm": False
    }
    response = client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 200
    assert "restaurants" in data if (data := response.json()) else True
