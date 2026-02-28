from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RecommendationQuery(BaseModel):
    location: Optional[str] = Field(
        default=None,
        description="Preferred location or area name (e.g., 'Banashankari').",
    )
    cuisines: List[str] = Field(
        default_factory=list,
        description="Preferred cuisines (e.g., ['North Indian', 'Chinese']).",
    )
    min_rating: float = Field(
        default=0.0, ge=0.0, le=5.0, description="Minimum average rating threshold."
    )
    budget_min: Optional[int] = Field(
        default=None, ge=0, description="Minimum approximate cost for two."
    )
    budget_max: Optional[int] = Field(
        default=None, ge=0, description="Maximum approximate cost for two."
    )
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum number of restaurants to return."
    )

    @field_validator("budget_max")
    @classmethod
    def validate_budget_range(cls, v: Optional[int], info) -> Optional[int]:
        # For Pydantic v2, use `info.data` to access already-validated fields.
        data = getattr(info, "data", {}) or {}
        budget_min = data.get("budget_min")
        if v is not None and budget_min is not None and v < budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return v


class RestaurantOut(BaseModel):
    id: int
    name: str
    location: Optional[str]
    rating: Optional[float]
    votes: Optional[int]
    cuisines: List[str] = Field(default_factory=list)
    approx_cost_for_two: Optional[int]
    # Phase 3 (LLM) fields – optional and only populated when LLM ranking is used.
    explanation: Optional[str] = Field(
        default=None,
        description="Short natural-language explanation for why this restaurant was recommended.",
    )
    llm_score: Optional[float] = Field(
        default=None,
        description="Optional score (0..1) from the LLM re-ranking stage.",
    )
    llm_rank: Optional[int] = Field(
        default=None,
        description="Rank assigned by the LLM (1-based), if applicable.",
    )
    badges: List[str] = Field(
        default_factory=list,
        description="Dynamic badges awarded based on restaurant performance/ranking.",
    )


class RecommendationsMeta(BaseModel):
    total_candidates: int
    returned: int


class RecommendationsResponse(BaseModel):
    query: RecommendationQuery
    meta: RecommendationsMeta
    restaurants: List[RestaurantOut]
    summary: Optional[str] = Field(
        default=None,
        description="Optional high-level summary of recommendations from the LLM.",
    )

