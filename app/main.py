from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
import os
import time
import uuid

from app.core.config import settings
from app.schemas.recommendations import (
    RecommendationQuery,
    RecommendationsMeta,
    RecommendationsResponse,
    RestaurantOut,
)
from app.services.dataset_loader import get_restaurants_index
from app.services.filtering_engine import filter_restaurants
from app.services.ranking_engine import rank_restaurants
from app.llm.groq_ranker import GroqRanker

# Phase 4 & 5 Imports
from app.phase4.cache_service import global_recommendation_cache, get_query_cache_key
from app.phase4.circuit_breaker import groq_circuit_breaker
from app.phase4.health_check import run_readiness_check, ReadinessResponse
from app.phase4.logger import service_logger
from app.phase5.meta_service import get_filter_metadata


app = FastAPI(title="AI Restaurant Recommendation Service", version="0.1.0")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://zomato-ai-restaurant-recommendation.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())
    # Attach request ID to state for logging
    request.state.request_id = request_id
    
    response: Response = await call_next(request)
    
    process_time = time.perf_counter() - start_time
    service_logger.log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=process_time * 1000,
        request_id=request_id
    )
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/live", tags=["meta"])
def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", response_model=ReadinessResponse, tags=["meta"])
def health_ready() -> ReadinessResponse:
    return run_readiness_check()


@app.get("/api/v1/meta/filters", tags=["meta"])
def meta_filters() -> dict:
    """Returns dynamic filter options (locations, cuisines, prices)."""
    return get_filter_metadata()


# Mount the frontend's static directory (Phase 5).
# This assumes a 'frontend/dist' folder exists after build.
frontend_path = os.path.join(os.getcwd(), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")


@app.post(
    "/api/v1/recommendations",
    response_model=RecommendationsResponse,
    tags=["recommendations"],
)
async def get_recommendations(query: RecommendationQuery, request: Request) -> RecommendationsResponse:
    request_id = getattr(request.state, "request_id", None)
    
    # 1. Cache Lookup (Phase 4)
    cache_key = get_query_cache_key(query)
    cached_response = global_recommendation_cache.get(cache_key)
    if cached_response:
        service_logger.logger.info(f"Cache hit for query: {cache_key}")
        return cached_response

    start_time = time.perf_counter()
    base_df = get_restaurants_index()

    filtered = filter_restaurants(base_df, query)
    total_candidates = filtered.height

    if total_candidates == 0:
        resp = RecommendationsResponse(
            query=query,
            meta=RecommendationsMeta(total_candidates=0, returned=0),
            restaurants=[],
        )
        global_recommendation_cache.set(cache_key, resp)
        return resp

    ranked = rank_restaurants(filtered, query)
    top = ranked.head(query.max_results)

    # Default: heuristic-only ordering.
    restaurants = [
        RestaurantOut(
            id=row["id"],
            name=row["name"],
            location=row.get("location"),
            rating=row.get("rating_numeric"),
            votes=row.get("votes"),
            cuisines=row.get("cuisines_normalized") or [],
            approx_cost_for_two=row.get("approx_cost_for_two"),
        )
        for row in top.to_dicts()
    ]

    llm_used = False
    llm_summary = None
    processing_ms = {"filtering_ranking": (time.perf_counter() - start_time) * 1000}

    # 2. LLM-based re-ranking with Circuit Breaker (Phase 4)
    if settings.USE_LLM_RANKING and settings.GROQ_API_KEY:
        if groq_circuit_breaker.state == groq_circuit_breaker.state.OPEN:
            service_logger.log_error("Groq circuit is OPEN, skipping LLM", request_id=request_id)
        else:
            llm_start = time.perf_counter()
            ranker = GroqRanker()
            try:
                # Wrap the re-rank call in the circuit breaker
                llm_result = await groq_circuit_breaker.acall(
                    ranker.re_rank,
                    query,
                    candidates=top,
                    max_candidates=settings.MAX_LLM_CANDIDATES,
                )
                
                if llm_result is not None:
                    llm_used = True
                    # Build a fast lookup from restaurant ID to index + object.
                    by_id = {r.id: r for r in restaurants}
                    reordered: list[RestaurantOut] = []
                    for item in llm_result.restaurants:
                        base = by_id.get(item.id)
                        if not base:
                            continue
                        base.explanation = item.explanation
                        base.llm_score = item.score
                        base.llm_rank = item.rank
                        reordered.append(base)
                    
                    # Preserve any restaurants not mentioned by the LLM at the end.
                    remaining = [r for r in restaurants if r.id not in {i.id for i in llm_result.restaurants}]
                    restaurants = reordered + remaining
                    llm_summary = llm_result.summary
                else:
                    service_logger.log_error("LLM re-ranking failed (None returned)", request_id=request_id)
            except Exception as e:
                service_logger.log_error("LLM call exception", error=e, request_id=request_id)
            finally:
                await ranker.aclose()
                processing_ms["llm"] = (time.perf_counter() - llm_start) * 1000

    # Calculate thresholds for badges based on candidates (Phase 5)
    votes_threshold = top["votes"].quantile(0.8) if top.height > 0 and "votes" in top.columns else None
    cost_threshold = top["approx_cost_for_two"].quantile(0.3) if top.height > 0 and "approx_cost_for_two" in top.columns else None

    # Final Deduplication, Explanation default, and Badges (Phase 5 Hardening)
    seen_ids = set()
    deduplicated_restaurants = []
    for r in restaurants:
        if r.id not in seen_ids:
            if r.explanation is None:
                r.explanation = "Solid overall option with balanced rating and cuisine fit."
            
            # Dynamic Badge Assignment
            r.badges = []
            if getattr(r, "llm_rank", None) == 1:
                r.badges.append("Top Pick")
            if votes_threshold is not None and r.votes is not None and r.votes >= votes_threshold:
                r.badges.append("Highly Popular")
            if cost_threshold is not None and r.approx_cost_for_two is not None and r.approx_cost_for_two <= cost_threshold:
                if r.rating is not None and r.rating >= 4:
                    r.badges.append("Best Value")
            if r.rating is not None and r.rating >= 4.2:
                r.badges.append("Top Rated")

            deduplicated_restaurants.append(r)
            seen_ids.add(r.id)
    restaurants = deduplicated_restaurants

    meta = RecommendationsMeta(
        total_candidates=total_candidates,
        returned=len(restaurants),
    )

    response = RecommendationsResponse(
        query=query, 
        meta=meta, 
        restaurants=restaurants, 
        summary=llm_summary
    )
    
    # 3. Store in Cache (Phase 4)
    global_recommendation_cache.set(cache_key, response)
    
    return response

