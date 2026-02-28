"""
Dataset ingestion and normalization utilities for the Zomato restaurant dataset.

Phase 1 responsibilities:
- Download/load the raw dataset from HuggingFace.
- Normalize key fields (rating, cost, location, cuisines).
- Persist a processed parquet file for efficient downstream use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import os

from app.core.config import settings

# Configure HuggingFace cache directories to live inside the project workspace
# before importing `datasets`, so that all cache writes stay within the
# sandboxed, writable directory tree.
hf_home = settings.DATA_DIR / "hf_home"
hf_cache = settings.RAW_CACHE_DIR
os.environ.setdefault("HF_HOME", str(hf_home))
os.environ.setdefault("HF_DATASETS_CACHE", str(hf_cache))
hf_home.mkdir(parents=True, exist_ok=True)
hf_cache.mkdir(parents=True, exist_ok=True)

import polars as pl
from datasets import load_dataset


_INDEX: Optional[pl.DataFrame] = None


def _ensure_directories() -> None:
    """Ensure that local data directories exist."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_dataset():
    """
    Load the raw Zomato dataset from HuggingFace.

    The datasets library will cache data under the HF cache dir, which we
    have configured (via environment variables) to live inside the project
    workspace.
    """
    return load_dataset(settings.HF_DATASET_NAME, split=settings.HF_DATASET_SPLIT)


def _normalize_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """
    Apply normalization steps to the raw restaurants dataframe.

    Expected input columns include (but are not limited to):
    - 'url', 'address', 'name', 'online_order', 'book_table', 'rate', 'votes',
      'phone', 'location', 'rest_type', 'dish_liked', 'cuisines',
      'approx_cost(for two people)', 'reviews_list', 'menu_item',
      'listed_in(type)', 'listed_in(city)'.
    """
    # 1. Deduplicate the raw data.
    initial_count = df.height
    print(f"[DEBUG] Rows before deduplication: {initial_count}")

    # Create internal normalization columns for a robust dedup key
    # We use name, location, and address as requested.
    df = df.with_columns([
        pl.col("name").cast(pl.Utf8).str.to_lowercase().str.strip_chars().fill_null("").alias("_name_norm"),
        pl.col("location").cast(pl.Utf8).str.to_lowercase().str.strip_chars().fill_null("").alias("_loc_norm"),
        pl.col("address").cast(pl.Utf8).str.to_lowercase().str.strip_chars().fill_null("").alias("_addr_norm")
    ])
    
    df = df.with_columns(
        (pl.col("_name_norm") + "|" + pl.col("_loc_norm") + "|" + pl.col("_addr_norm")).alias("dedup_key")
    )

    # Sort by votes descending to keep the most popular entry
    if "votes" in df.columns:
        df = df.sort("votes", descending=True)
    
    # Perform deduplication
    df = df.unique(subset=["dedup_key"], keep="first")
    
    # Remove temporary internal columns
    df = df.drop(["_name_norm", "_loc_norm", "_addr_norm", "dedup_key"])

    final_count = df.height
    print(f"[DEBUG] Rows after deduplication: {final_count} (removed {initial_count - final_count})")

    # 2. Add a stable integer ID based on row position AFTER deduplication.
    df = df.with_columns(pl.arange(0, pl.len()).alias("id"))

    # 3. Normalize rating: extract leading numeric from strings like "4.1/5".
    df = df.with_columns(
        pl.col("rate")
        .cast(pl.Utf8)
        .str.extract(r"([\d.]+)", 1)
        .cast(pl.Float64, strict=False)
        .alias("rating_numeric")
    )

    # 4. Normalize approximate cost for two: strip commas and cast to integer.
    cost_col = "approx_cost(for two people)"
    if cost_col in df.columns:
        df = df.with_columns(
            pl.col(cost_col)
            .cast(pl.Utf8)
            .str.replace_all(",", "")
            .str.extract(r"(\d+)", 1)
            .cast(pl.Int64, strict=False)
            .alias("approx_cost_for_two")
        )
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("approx_cost_for_two"))

    # 5. Normalized location key for grouping/lookup.
    if "location" in df.columns:
        df = df.with_columns(
            pl.col("location")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.strip_chars()
            .alias("location_normalized")
        )
    else:
        df = df.with_columns(
            pl.lit(None, dtype=pl.Utf8).alias("location_normalized")
        )

    # 6. Cuisines as normalized list of strings.
    if "cuisines" in df.columns:
        df = df.with_columns(
            pl.col("cuisines")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.split(",")
            .list.eval(pl.element().str.strip_chars())
            .alias("cuisines_normalized")
        )
    else:
        df = df.with_columns(
            pl.lit(None, dtype=pl.List(pl.Utf8)).alias("cuisines_normalized")
        )

    return df


def build_restaurants_index(
    limit: Optional[int] = None, force_rebuild: bool = False
) -> pl.DataFrame:
    """
    Build (or reload) the normalized restaurants index as a Polars DataFrame.

    - If a processed parquet file exists and `force_rebuild` is False, it is reused.
    - Otherwise, the raw dataset is loaded from HuggingFace, normalized, and written.
    - `limit` can be used to restrict the number of rows for testing purposes.
    """
    _ensure_directories()
    processed_path: Path = settings.PROCESSED_DATASET_PATH

    if processed_path.exists() and not force_rebuild:
        df = pl.read_parquet(processed_path)
        if limit is not None:
            return df.head(limit)
        return df

    raw_ds = load_raw_dataset()

    # Optionally limit records for local testing.
    if limit is not None:
        raw_ds = raw_ds.select(range(limit))

    # Convert to pandas then to polars for convenience.
    pandas_df = raw_ds.to_pandas()
    df = pl.from_pandas(pandas_df)

    df = _normalize_dataframe(df)

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(processed_path)

    if limit is not None:
        return df.head(limit)
    return df


def get_restaurants_index(
    limit: Optional[int] = None, force_rebuild: bool = False
) -> pl.DataFrame:
    """
    Retrieve the in-memory restaurants index, building or reloading as necessary.

    This is the canonical entrypoint other parts of the backend should use.
    """
    global _INDEX

    if _INDEX is None or force_rebuild:
        _INDEX = build_restaurants_index(limit=None, force_rebuild=force_rebuild)

    if limit is not None:
        return _INDEX.head(limit)
    return _INDEX

