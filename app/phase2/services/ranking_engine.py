from __future__ import annotations

from typing import Iterable, Optional

import polars as pl

from app.schemas.recommendations import RecommendationQuery


def _normalize_cuisines(cuisines: Optional[Iterable[str]]) -> list[str]:
    if not cuisines:
        return []
    return [c.lower().strip() for c in cuisines if c and c.strip()]


def rank_restaurants(
    df: pl.DataFrame,
    query: RecommendationQuery,
) -> pl.DataFrame:
    """
    Apply a heuristic scoring function and return a ranked dataframe.

    Score components:
    - normalized rating
    - popularity (log of votes)
    - cuisine match bonus
    """
    normalized_cuisines = _normalize_cuisines(query.cuisines)

    rating_term = (pl.col("rating_numeric").fill_null(0) / 5.0).alias("rating_term")
    votes_term = (
        (pl.col("votes").fill_null(0).cast(pl.Float64) + 1.0)
        .log10()
        .fill_null(0.0)
        .alias("votes_term")
    )

    if normalized_cuisines:
        match_count = (
            pl.col("cuisines_normalized")
            .list.set_intersection(pl.lit(normalized_cuisines))
            .list.len()
            .fill_null(0)
        )
        cuisine_bonus = (match_count / float(len(normalized_cuisines))).alias(
            "cuisine_bonus"
        )
    else:
        cuisine_bonus = pl.lit(0.0).alias("cuisine_bonus")

    scored = df.with_columns(
        [
            rating_term,
            votes_term,
            cuisine_bonus,
        ]
    ).with_columns(
        (
            0.6 * pl.col("rating_term")
            + 0.3 * pl.col("votes_term")
            + 0.1 * pl.col("cuisine_bonus")
        ).alias("score")
    )

    return scored.sort(
        ["score", "rating_numeric", "votes"],
        descending=[True, True, True],
    )

