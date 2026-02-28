from __future__ import annotations

from typing import Iterable, Optional

import polars as pl

from app.schemas.recommendations import RecommendationQuery


def _normalize_cuisines(cuisines: Optional[Iterable[str]]) -> list[str]:
    if not cuisines:
        return []
    return [c.lower().strip() for c in cuisines if c and c.strip()]


def filter_restaurants(
    df: pl.DataFrame,
    query: RecommendationQuery,
) -> pl.DataFrame:
    """
    Apply Phase 2 hard filters to the restaurants dataframe.

    Filters:
    - location (substring match on normalized location)
    - minimum rating
    - budget range
    - cuisine intersection
    """
    mask = pl.lit(True)

    # Location filter (substring match on normalized location).
    if query.location:
        loc = query.location.lower().strip()
        if loc:
            location_match = (
                pl.col("location_normalized")
                .str.contains(loc)
                .fill_null(False)
            )
            mask = mask & location_match

    # Rating filter.
    if query.min_rating is not None:
        rating_match = pl.col("rating_numeric").fill_null(0) >= query.min_rating
        mask = mask & rating_match

    # Budget filters.
    cost_col = pl.col("approx_cost_for_two")
    if query.budget_min is not None:
        mask = mask & ((cost_col >= query.budget_min) | cost_col.is_null())
    if query.budget_max is not None:
        mask = mask & ((cost_col <= query.budget_max) | cost_col.is_null())

    # Cuisine filter (intersection must be non-empty).
    normalized_cuisines = _normalize_cuisines(query.cuisines)
    if normalized_cuisines:
        intersect_len = (
            pl.col("cuisines_normalized")
            .list.set_intersection(pl.lit(normalized_cuisines))
            .list.len()
            .fill_null(0)
        )
        cuisine_match = intersect_len > 0
        mask = mask & cuisine_match

    return df.filter(mask)

