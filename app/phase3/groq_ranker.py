from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
import polars as pl

from app.core.config import settings
from app.schemas.recommendations import RecommendationQuery


logger = logging.getLogger(__name__)


@dataclass
class LLMRankedRestaurant:
    id: int
    explanation: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None


@dataclass
class LLMRecommendationResult:
    restaurants: List[LLMRankedRestaurant]
    summary: Optional[str] = None


class GroqRanker:
    """
    Thin wrapper around Groq's Chat Completions API for re-ranking candidates.
    Falls back safely if anything fails.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            timeout=self.timeout_seconds,
        )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def re_rank(
        self,
        query: RecommendationQuery,
        candidates: pl.DataFrame,
        max_candidates: Optional[int] = None,
    ) -> Optional[LLMRecommendationResult]:

        if not self.is_configured():
            logger.info("GroqRanker not configured; skipping LLM re-ranking.")
            return None

        if candidates.height == 0:
            return None

        if max_candidates and candidates.height > max_candidates:
            candidates = candidates.head(max_candidates)

        payload = self._build_payload(query, candidates)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # --- API Call ---
        try:
            response = await self._client.post(
                "/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("GroqRanker request failed: %s", exc)
            try:
                if hasattr(exc, "response") and exc.response is not None:
                    logger.warning("Groq response body: %s", exc.response.text)
            except Exception:
                pass
            return None

        # --- Robust Parsing ---
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if not content:
                logger.warning("Groq returned empty content.")
                return None

            content = content.strip()

            # Remove markdown code fences if present
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:].strip()

            # Extract first JSON object
            start = content.find("{")
            end = content.rfind("}")

            if start == -1 or end == -1:
                logger.warning("Groq content does not contain valid JSON: %s", content)
                return None

            json_str = content[start:end + 1]
            parsed = json.loads(json_str)

        except Exception as exc:
            logger.warning("GroqRanker response parse failed. Raw content: %s", content)
            return None

        return self._parse_result(parsed)

    def _build_payload(
        self, query: RecommendationQuery, candidates: pl.DataFrame
    ) -> Dict:

        user_prefs = {
            "location": query.location,
            "cuisines": query.cuisines,
            "min_rating": query.min_rating,
            "budget_min": query.budget_min,
            "budget_max": query.budget_max,
        }

        candidate_list: List[Dict] = []

        for row in candidates.to_dicts():
            candidate_list.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "location": row.get("location"),
                    "rating": row.get("rating_numeric"),
                    "votes": row.get("votes"),
                    "cuisines": row.get("cuisines_normalized") or [],
                    "approx_cost_for_two": row.get("approx_cost_for_two"),
                }
            )

        system_msg = (
            "You are ranking restaurants based on user preferences.\n\n"
            "Prioritize:\n"
            "  1. Strength of requested cuisine match.\n"
            "  2. Rating quality.\n"
            "  3. Popularity.\n"
            "  4. Budget alignment.\n\n"
            "Each explanation must:\n"
            "  - Start with strongest cuisine relevance.\n"
            "  - Mention one tradeoff if present.\n"
            "  - Be under 18 words.\n"
            "  - Avoid generic phrases like \"steady favorite\" or \"niche spot\".\n"
            "  - Avoid repetition across restaurants.\n\n"
            "Return strict JSON:\n"
            "{\n"
            '  "summary": "one sentence",\n'
            '  "restaurants": [\n'
            '    { "id": int, "rank": int, "score": float, "explanation": string }\n'
            "  ]\n"
            "}\n\n"
            "Do not invent restaurants."
        )

        user_msg = {
            "user_preferences": user_prefs,
            "candidates": candidate_list,
        }

        return {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": json.dumps(user_msg),
                },
            ],
        }

    def _parse_result(self, payload: Dict) -> Optional[LLMRecommendationResult]:

        if "restaurants" not in payload:
            return None

        items = []

        for idx, item in enumerate(payload["restaurants"]):
            try:
                rid = int(item["id"])
            except Exception:
                continue

            explanation = item.get("explanation")
            score = item.get("score")

            try:
                score_f = float(score) if score is not None else None
            except Exception:
                score_f = None

            items.append(
                LLMRankedRestaurant(
                    id=rid,
                    explanation=explanation,
                    score=score_f,
                    rank=idx + 1,
                )
            )

        if not items:
            return None

        return LLMRecommendationResult(
            restaurants=items, 
            summary=payload.get("summary")
        )