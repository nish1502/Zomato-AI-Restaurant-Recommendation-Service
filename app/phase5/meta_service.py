from __future__ import annotations
import polars as pl
from typing import Dict, Any
from app.services.dataset_loader import get_restaurants_index


def get_filter_metadata() -> Dict[str, Any]:
    """
    Extract unique filter values from dataset.
    Now supports cuisines grouped by location.
    """

    df = get_restaurants_index()
    df = df.drop_nulls("location")

    # Unique locations
    locations = (
        df.select("location")
        .unique()
        .sort("location")
        .to_series()
        .to_list()
    )

    # Cuisines grouped by location
    cuisines_by_location = {}

    for loc in locations:
        cuisines = (
            df.filter(pl.col("location") == loc)
            .select(pl.col("cuisines_normalized").list.explode())
            .drop_nulls()
            .unique()
            .sort("cuisines_normalized")
            .to_series()
            .to_list()
        )
        cuisines_by_location[loc] = cuisines

    price_bands = [
        {"id": "low", "label": "₹0–₹400", "min": 0, "max": 400},
        {"id": "medium", "label": "₹400–₹800", "min": 400, "max": 800},
        {"id": "high", "label": "₹800+", "min": 800, "max": None},
    ]

    rating_steps = [3.0, 3.5, 4.0, 4.5]

    return {
        "locations": locations,
        "cuisines_by_location": cuisines_by_location,
        "price_bands": price_bands,
        "rating_steps": rating_steps,
    }