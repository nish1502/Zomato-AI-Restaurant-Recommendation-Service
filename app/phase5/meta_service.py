from __future__ import annotations
import polars as pl
from typing import Dict, List, Any
from app.services.dataset_loader import get_restaurants_index

def get_filter_metadata() -> Dict[str, Any]:
    """
    Extracts unique filter values from the restaurant dataset.
    Used by the frontend to populate dropdowns and sliders.
    """
    df = get_restaurants_index()
    
    # 1. Unique Locations (sorted)
    locations = (
        df.select("location")
        .drop_nulls()
        .unique()
        .sort("location")
        .to_series()
        .to_list()
    )
    
    # 2. Unique Cuisines (flattened from lists)
    cuisines = (
        df.select(pl.col("cuisines_normalized").list.explode())
        .drop_nulls()
        .unique()
        .sort("cuisines_normalized")
        .to_series()
        .to_list()
    )
    
    # 3. Static Price Bands (based on architecture doc 4.2.3)
    price_bands = [
        {"id": "low", "label": "₹0–₹400", "min": 0, "max": 400},
        {"id": "medium", "label": "₹400–₹800", "min": 400, "max": 800},
        {"id": "high", "label": "₹800+", "min": 800, "max": None},
    ]
    
    # 4. Rating Steps
    rating_steps = [3.0, 3.5, 4.0, 4.5]
    
    return {
        "locations": locations,
        "cuisines": cuisines,
        "price_bands": price_bands,
        "rating_steps": rating_steps,
    }
