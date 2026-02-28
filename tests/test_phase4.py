import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.phase4.cache_service import global_recommendation_cache, get_query_cache_key
from app.phase4.circuit_breaker import CircuitBreaker, CircuitState
from app.schemas.recommendations import RecommendationQuery

client = TestClient(app)

def test_health_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "dependencies" in data
    assert "dataset" in data["dependencies"]
    assert "groq_llm" in data["dependencies"]

def test_cache_mechanism():
    # Clear cache first
    global_recommendation_cache.clear()
    
    query_data = {
        "location": "Banashankari",
        "cuisines": ["North Indian"],
        "min_rating": 3.0,
        "max_results": 5
    }
    
    # First request
    resp1 = client.post("/api/v1/recommendations", json=query_data)
    assert resp1.status_code == 200
    request_id1 = resp1.headers.get("X-Request-ID")
    
    # Second request (same query)
    resp2 = client.post("/api/v1/recommendations", json=query_data)
    assert resp2.status_code == 200
    request_id2 = resp2.headers.get("X-Request-ID")
    
    # They should have the same content (mostly) but different request IDs if they went through the middleware
    # Actually, the middleware runs for every request, but the logic inside returns early for cache hits
    assert resp1.json() == resp2.json()
    
    # Check if process time header exists
    assert "X-Process-Time" in resp1.headers
    assert "X-Process-Time" in resp2.headers

def test_circuit_breaker_unit():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=1, name="test_cb")
    
    def failing_func():
        raise ValueError("Failed")
        
    def success_func():
        return "Success"
    
    # 1. Start closed
    assert cb.state == CircuitState.CLOSED
    
    # 2. First failure
    res = cb.call(failing_func)
    assert res is None
    assert cb.failure_count == 1
    assert cb.state == CircuitState.CLOSED
    
    # 3. Second failure -> Opens
    res = cb.call(failing_func)
    assert res is None
    assert cb.failure_count == 2
    assert cb.state == CircuitState.OPEN
    
    # 4. While open, returns None immediately without calling func
    res = cb.call(success_func)
    assert res is None
    
    # 5. Wait for recovery timeout (mocking or sleeping)
    import time
    time.sleep(1.1)
    
    # 6. Should be Half-Open on next call
    # In my implementation, _update_state moves to HALF_OPEN
    res = cb.call(success_func)
    assert res == "Success"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

def test_query_cache_key_stability():
    q1 = RecommendationQuery(location="A", cuisines=["B"], min_rating=4.0)
    q2 = RecommendationQuery(location="A", cuisines=["B"], min_rating=4.0)
    q3 = RecommendationQuery(location="A", cuisines=["C"], min_rating=4.0)
    
    assert get_query_cache_key(q1) == get_query_cache_key(q2)
    assert get_query_cache_key(q1) != get_query_cache_key(q3)
