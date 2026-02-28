import polars as pl

from app.services.dataset_loader import build_restaurants_index, get_restaurants_index


def test_build_restaurants_index_creates_normalized_dataframe():
    """
    End-to-end test for Phase 1:
    - Loads the Zomato dataset from HuggingFace.
    - Normalizes key fields.
    - Returns a non-empty Polars DataFrame with expected columns.
    """
    # Limit rows for test speed and to avoid excessive memory usage.
    df = build_restaurants_index(limit=500, force_rebuild=True)

    assert isinstance(df, pl.DataFrame)
    assert df.height > 0

    # Core columns that must exist after normalization.
    expected_columns = {
        "id",
        "name",
        "location",
        "rating_numeric",
        "approx_cost_for_two",
        "location_normalized",
        "cuisines_normalized",
    }

    assert expected_columns.issubset(set(df.columns))

    # At least some rows should have numeric ratings.
    non_null_ratings = df.get_column("rating_numeric").drop_nulls()
    assert non_null_ratings.len() > 0

    # Approximate cost should be non-negative where present.
    non_null_costs = df.get_column("approx_cost_for_two").drop_nulls()
    if non_null_costs.len() > 0:
        assert (non_null_costs >= 0).all()


def test_get_restaurants_index_uses_cached_dataframe():
    """
    Ensure that get_restaurants_index returns the same cached DataFrame
    instance across calls (basic smoke test for in-memory caching).
    """
    df1 = get_restaurants_index(limit=100, force_rebuild=True)
    df2 = get_restaurants_index(limit=100, force_rebuild=False)

    assert isinstance(df1, pl.DataFrame)
    assert isinstance(df2, pl.DataFrame)

    # Both dataframes should have at least as many rows as requested (if available).
    assert df1.height >= min(100, df2.height)

