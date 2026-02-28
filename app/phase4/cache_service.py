from __future__ import annotations
import collections
import hashlib
import json
from typing import Any, Hashable
from app.schemas.recommendations import RecommendationQuery

class LRUCache:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key: Hashable) -> Any | None:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: Hashable, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        self.cache.clear()

def get_query_cache_key(query: RecommendationQuery) -> str:
    """Generates a stable cache key for a recommendation query."""
    query_dict = query.model_dump()
    query_str = json.dumps(query_dict, sort_keys=True)
    return hashlib.sha256(query_str.encode()).hexdigest()

global_recommendation_cache = LRUCache(capacity=50)
