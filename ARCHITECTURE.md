## AI Restaurant Recommendation Service – Architecture

This document describes the production-oriented architecture of the AI Restaurant Recommendation Service.

The system:
- Ingests and normalizes the Zomato dataset from HuggingFace: [`zomato-restaurant-recommendation`](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)
- Exposes a FastAPI backend consumed by a React frontend
- Uses Groq LLM for intelligent ranking and natural-language explanations
- Targets scalable, observable, and maintainable deployment

---

## 1. High-Level System Design & Data Flow

### 1.1 Core Components

- **Client (Web)**: React SPA
  - Preference input form (location, budget, cuisine, minimum rating, optional free-text preferences)
  - Results list with explanations, filters, and pagination
- **Backend API**: Python FastAPI
  - Public REST API consumed by frontend
  - Orchestrates dataset query, ranking, and LLM calls
- **Data Layer**
  - **Raw dataset**: CSV downloaded from HuggingFace
  - **Processed store**:
    - Early phases: Local Parquet and in-memory DataFrame (e.g., Polars or Pandas)
    - Production: Relational DB (e.g., Postgres) and/or columnar store (e.g., DuckDB/Parquet) for analytics
- **Recommendation Engine (Backend services)**
  - Filtering engine (hard constraints)
  - Heuristic pre-ranking (ratings, votes, distance, cost)
  - LLM-based re-ranking & explanation (Groq)
- **LLM Provider**
  - Groq-hosted models (e.g., `llama-3.1-70b-versatile` or similar)
  - Securely called from backend only
- **Infra / Observability**
  - Containerized services (Docker)
  - Deployed behind a load balancer (e.g., Nginx / cloud LB)
  - Metrics, logging, tracing, and basic alerting

### 1.2 End-to-End Request Flow

1. **User submits preferences** from React:
   - Location (city/area text)
   - Budget range
   - Cuisine(s)
   - Minimum rating
   - Optional: dietary tags, occasion, free-text notes
2. **Frontend sends POST** `/api/v1/recommendations` with structured JSON.
3. **FastAPI validates request** (Pydantic models) and:
   - Normalizes inputs (e.g., case-folding, canonical location/cuisine names)
4. **Filtering engine**:
   - Queries pre-loaded restaurant index (in-memory or DB)
   - Applies hard filters:
     - Match on location (exact or fuzzy/clustered)
     - Price band approximated from `approx_cost(for two people)`
     - Cuisine inclusion
     - `rate` ≥ minimum rating
   - Produces a **candidate set** (e.g., top 100–200 restaurants).
5. **Heuristic pre-ranking**:
   - Assigns base score using:
     - Rating (normalized)
     - Number of votes (popularity)
     - Text features (e.g., presence of user-requested dishes/cuisines)
   - Truncates list to a smaller subset (e.g., 20–50) for LLM.
6. **LLM ranking & explanation** (if enabled for this request):
   - Backend prepares a compact prompt summarizing:
     - User preferences
     - Candidate restaurant metadata
   - Calls Groq LLM for:
     - Reordered ranking
     - Per-restaurant explanation snippets
     - Optional overall summary paragraph
   - Applies sanity checks (ensure candidate IDs are preserved & valid).
7. **Backend constructs response**:
   - Final ordered list of restaurants
   - Structured metadata (scores, explanations, reasons)
8. **Frontend renders results**:
   - List/grid view, with filters and sort options
   - Shows explanations and any overall narrative
9. **Telemetry**:
   - Request & latency metrics
   - LLM token usage & errors
   - Optional anonymized feedback events

---

## 2. Backend Modular Structure

The FastAPI backend is organized for extensibility and testability.

### 2.1 Suggested Package Layout

- `app/`
  - `main.py`  
    - FastAPI app instantiation, router inclusion, startup/shutdown events.
  - `core/`
    - `config.py` – environment-based configuration (dataset paths, Groq keys, feature flags, limits).
    - `logging.py` – logging setup, request/response logging middleware.
    - `security.py` – API keys / auth hooks (if needed), rate-limiting integration stubs.
  - `api/`
    - `deps.py` – shared dependencies (e.g., DB session, data index, configuration injection).
    - `v1/`
      - `routes_recommendations.py` – `/recommendations` endpoint.
      - `routes_meta.py` – `/meta/filters` endpoint.
      - `routes_health.py` – health & readiness endpoints.
  - `schemas/`
    - `recommendations.py` – request/response Pydantic models.
    - `restaurant.py` – restaurant DTOs.
    - `common.py` – pagination, error schemas.
  - `services/`
    - `dataset_loader.py` – ingestion and preprocessing of dataset; building indices.
    - `filtering_engine.py` – core filtering logic.
    - `ranking_engine.py` – heuristic scoring & ordering.
    - `llm_ranker.py` – Groq integration, prompt templates, re-ranking logic.
    - `location_matcher.py` – location normalization/matching strategy.
    - `cuisine_normalizer.py` – standardization of cuisine tokens.
  - `repositories/`
    - `restaurants_repo.py` – abstractions over data store(s): query by filters, fetch by IDs.
  - `models/`
    - If using ORM: SQLAlchemy models for restaurants and derived tables.
  - `infra/` (optional)
    - `db.py` – DB connection/session management.
    - `cache.py` – Redis or in-memory LRU cache helpers.
    - `metrics.py` – Prometheus metrics registration.
  - `tests/`
    - Unit tests for services and APIs.
    - Integration tests for end-to-end flows.

### 2.2 Design Principles

- **Separation of concerns**: API layer thin; all logic in `services/` and `repositories/`.
- **Data abstraction**: `restaurants_repo` hides storage choice (DataFrame vs DB) for easy migration.
- **LLM isolation**: All Groq-related logic in `llm_ranker.py` with a well-defined interface:
  - Input: user preferences + candidate list
  - Output: reordered list + explanations
- **Configuration-driven behavior**:
  - Feature flags:
    - `USE_LLM_RANKING` (fallback to heuristic only)
    - `MAX_LLM_CANDIDATES`
    - `MAX_RESULTS_PER_REQUEST`

---

## 3. Phased Development Plan

### Phase 0 – Foundations & Environment

- **Goals**
  - Set up repo, environments, basic CI/CD, and skeleton backend/frontend.
- **Backend**
  - Initialize FastAPI project structure as above.
  - Add basic `/health` and `/version` endpoints.
  - Configure logging, `.env` management, and Dockerfile.
- **Frontend**
  - Create React app (Vite or CRA).
  - Set up routing and a basic page layout.
- **Infra**
  - CI pipeline:
    - Lint (e.g., ruff, black) and tests on PRs.
  - Dev and staging environments (e.g., Docker Compose or cloud dev stack).

---

### Phase 1 – Dataset Ingestion & Normalization

- **Goals**
  - Download, parse, and normalize the Zomato dataset for efficient queries.
- **Data ingestion**
  - Implement `dataset_loader`:
    - Download CSV from HuggingFace or fetch once and store in object storage.
    - Parse CSV into a DataFrame (Polars recommended for performance).
  - Normalization steps:
    - Convert `rate` strings (e.g., `"4.1/5"`, `"NEW"`) into numeric float ratings or `null`.
    - Parse `approx_cost(for two people)` into numeric integers (strip commas).
    - Normalize `location`, `cuisines`, and `rest_type`:
      - Lowercase, trim spaces.
      - Split multi-cuisines into list tokens.
    - Clean `reviews_list` (optional at this phase; can store raw).
  - Persist processed data:
    - Write to local Parquet file(s) with typed schema.
    - Optionally load into Postgres/DuckDB for exploration.
- **Backend integration**
  - On app startup:
    - Load Parquet into an in-memory index (DataFrame / typed objects).
    - Pre-compute helpful derived fields:
      - `normalized_location_key`
      - `rating_numeric`
      - Tokenized cuisines set.
- **Testing**
  - Unit tests validating normalization logic and handling of edge cases.

---

### Phase 2 – Filtering Engine & Baseline Recommendations

- **Goals**
  - Implement robust, fast filtering and heuristic ranking, without LLM.
- **Filtering engine (`filtering_engine.py`)**
  - Input: typed `RecommendationRequest`.
  - Steps:
    - Location filter:
      - Start simple: exact or partial match on `location` field.
      - Later: alias/cluster table (e.g., “Banashankari 2nd Stage” variants).
    - Rating filter:
      - `rating_numeric >= min_rating`.
    - Budget filter:
      - Map `approx_cost(for two people)` to a range and intersect with user’s budget.
    - Cuisine filter:
      - Intersection of requested cuisine tokens with restaurant’s cuisine set.
  - Output: candidate list (IDs + key fields).
- **Heuristic ranking (`ranking_engine.py`)**
  - Score calculation (example):
    - `score = α * normalized_rating + β * log(1 + votes) + γ * match_bonus`
    - `match_bonus` for:
      - More requested cuisines matched.
      - Restaurants in closer sub-location (if available).
  - Sort candidates by score descending.
  - Truncate to:
    - `MAX_RESULTS_PER_REQUEST` for final output, and
    - `MAX_LLM_CANDIDATES` for later LLM phases.
- **API**
  - Implement `/api/v1/recommendations` with baseline heuristic-only logic.
  - Implement `/api/v1/meta/filters` to return:
    - List of unique locations, cuisines, cost ranges (from precomputed stats).
- **Frontend**
  - Connect to baseline API.
  - Build basic filters UI and result view using heuristic recommendations only.

---

### Phase 3 – Groq LLM Integration (Intelligent Ranking & Explanation)

- **Goals**
  - Integrate Groq to refine ranking and generate natural-language explanations.
- **LLM service (`llm_ranker.py`)**
  - Responsibilities:
    - Prompt construction:
      - Summarize user preferences (structured bullets).
      - Include candidate restaurants with compact fields:
        - ID, name, location, rating, cuisines, cost band, high-level description (e.g., top review snippet).
      - Ask model to:
        - Re-order restaurants.
        - Provide short reason (1–2 sentences) per restaurant.
        - Optional: provide a short overview summary.
    - Call Groq API:
      - Use HTTP client with timeouts and retries.
      - Choose default model (e.g., `llama-3.1-70b-versatile` or current best for this use case).
    - Parse response into structured `LLMRecommendationResult`.
- **Backend orchestration**
  - Update `/recommendations` endpoint flow:
    - Apply filtering and heuristic scoring (Phase 2).
    - If `USE_LLM_RANKING` is enabled:
      - Select top `N` candidates for LLM.
      - Call `llm_ranker.re_rank(...)`.
      - Merge LLM ordering with base metadata.
    - If LLM times out or fails:
      - Log error, fall back to heuristic-only ranking.
- **Prompt design considerations**
  - Keep prompts compact to respect token limits.
  - Encode restaurants as numbered list, and require response using the same IDs.
  - Constraints:
    - Ask the model not to invent restaurants outside the provided list.
    - Limit explanation length to control tokens and latency.
- **Testing**
  - Unit tests for prompt construction (snapshot-style).
  - Mocked integration tests simulating Groq API responses.
  - Performance tests on end-to-end latency.

---

### Phase 4 – Optimization & Production Hardening

- **Goals**
  - Improve latency, reliability, and cost-efficiency for real-world usage.
- **Performance & caching**
  - Caching layers:
    - In-memory / Redis cache for:
      - Filtered candidate sets keyed by normalized preference tuple.
      - LLM outputs for repeated or very similar queries.
    - TTL-based invalidation.
  - Pre-computation:
    - Precompute location clusters and common queries (e.g., “Banashankari + North Indian + budget mid-range”).
  - Async I/O:
    - Use async HTTP client for Groq.
    - Ensure FastAPI runs with appropriate workers and concurrency model.
- **Data store hardening**
  - Migrate from memory-only DataFrame to:
    - Postgres (primary store) + read replicas for scaling, or
    - DuckDB/Parquet for high-throughput analytic-style queries.
  - Add indices on:
    - `location_key`
    - `rating_numeric`
    - `approx_cost_band`
    - `normalized_cuisines` (GIN index if using Postgres JSONB/array).
- **Monitoring & logging**
  - Expose metrics:
    - Request count, success/error rate.
    - P95 latencies (overall and LLM-specific).
    - LLM token usage & cost estimation.
    - Cache hit/miss rates.
  - Structured logs:
    - Correlation IDs per request.
    - Redact sensitive fields (no user PII).
- **Reliability**
  - Health checks:
    - `/health/live` – basic.
    - `/health/ready` – verifies dataset loaded, DB reachable, Groq reachable (optional).
  - Circuit breaker for LLM:
    - On repeated failures, temporarily disable LLM ranking and use heuristic-only path.

---

### Phase 5 – Frontend UI & UX

- **Goals**
  - Deliver a polished user experience and leverage intelligent explanations.
- **Core pages**
  - Home / Search:
    - Preference form (location autocomplete, sliders for budget/rating).
    - Advanced options (occasion, dietary restrictions, group size).
  - Results:
    - Ranked list with:
      - Name, rating, votes, cuisines, approximate cost.
      - Short explanation from LLM: “Recommended because…”
      - Highlights: matching cuisines, budget fit badge, “Great for family dinners” etc.
    - Sort / filter controls (client-side) that respect server ranking.
  - Details modal / page:
    - Show more info (liked dishes, review snippet).
    - “Why this recommendation?” – expanded explanation.
- **Frontend architecture**
  - API client:
    - Typed client middleware (e.g., Axios with interceptors).
    - Centralized error and loading handling.
  - State management:
    - React Query or similar for caching server responses.
  - Telemetry:
    - Client logs and basic analytics (e.g., which filters used, click-throughs).

---

## 4. API Design

### 4.1 Conventions

- Base path: `/api/v1`
- JSON over HTTPS
- All timestamps in ISO 8601 (if/when used)
- Errors use structured envelope with `code`, `message`, optional `details`.

### 4.2 Endpoints

#### 4.2.1 `GET /api/v1/health/live`

- **Purpose**: Liveness probe.
- **Response (200)**:

```json
{
  "status": "ok"
}
```

#### 4.2.2 `GET /api/v1/health/ready`

- **Purpose**: Readiness probe (dataset loaded, dependencies healthy).
- **Response (200)**:

```json
{
  "status": "ready",
  "dependencies": {
    "dataset_loaded": true,
    "database": "ok",
    "groq_llm": "ok"
  }
}
```

(`groq_llm` may be `"degraded"` if a circuit breaker is open.)

#### 4.2.3 `GET /api/v1/meta/filters`

- **Purpose**: Provide metadata for building client filters (locations, cuisines, price bands).
- **Response (200)**:

```json
{
  "locations": [
    "Banashankari",
    "Basavanagudi",
    "Mysore Road"
  ],
  "cuisines": [
    "North Indian",
    "South Indian",
    "Chinese",
    "Cafe",
    "Italian"
  ],
  "price_bands": [
    { "id": "low", "label": "₹0–₹400", "min": 0, "max": 400 },
    { "id": "medium", "label": "₹400–₹800", "min": 400, "max": 800 },
    { "id": "high", "label": "₹800+", "min": 800, "max": null }
  ],
  "rating_steps": [3.0, 3.5, 4.0, 4.5]
}
```

#### 4.2.4 `POST /api/v1/recommendations`

- **Purpose**: Main recommendations endpoint.
- **Request body**:

```json
{
  "location": "Banashankari",
  "cuisines": ["North Indian", "Chinese"],
  "min_rating": 4.0,
  "budget_min": 400,
  "budget_max": 900,
  "max_results": 10,
  "use_llm": true,
  "user_context": {
    "group_size": 4,
    "dietary_preferences": ["vegetarian_friendly"],
    "occasion": "family_dinner",
    "notes": "Prefer places with buffet and good ambience."
  }
}
```

- **Response (200)**:

```json
{
  "query": {
    "location": "Banashankari",
    "cuisines": ["North Indian", "Chinese"],
    "min_rating": 4.0,
    "budget_min": 400,
    "budget_max": 900,
    "use_llm": true
  },
  "meta": {
    "total_candidates": 87,
    "returned": 10,
    "llm_used": true,
    "processing_ms": {
      "filtering": 35,
      "heuristic_ranking": 8,
      "llm_ranking": 420,
      "total": 470
    }
  },
  "summary": "Here are 10 highly rated North Indian and Chinese restaurants in Banashankari that fit your budget and are well-suited for a family dinner with buffet options.",
  "restaurants": [
    {
      "id": "rest_58694",
      "name": "Jalsa",
      "location": "Banashankari",
      "rating": 4.1,
      "votes": 775,
      "cuisines": ["North Indian", "Mughlai", "Chinese"],
      "approx_cost_for_two": 800,
      "rest_type": "Casual Dining",
      "online_order": true,
      "book_table": true,
      "llm_rank": 1,
      "heuristic_score": 0.92,
      "llm_score": 0.97,
      "explanation": "Strong buffet, family-friendly ambience, and highly rated North Indian dishes within your budget."
    }
  ]
}
```

- **Error (400) example**:

```json
{
  "code": "INVALID_REQUEST",
  "message": "budget_min must be less than or equal to budget_max",
  "details": {
    "field": "budget_min"
  }
}
```

#### 4.2.5 (Optional) `POST /api/v1/feedback`

- **Purpose**: Collect optional user feedback (e.g., thumbs up/down) to improve heuristics.
- **Priority**: Phase 4+.

---

## 5. LLM Integration Strategy

### 5.1 Model Selection

- **Primary model**: Groq-hosted general-purpose LLM (e.g., `llama-3.1-70b-versatile` or latest comparable).
- **Criteria**:
  - Good reasoning for ranking trade-offs (budget vs rating vs ambience).
  - Controlled latency and token efficiency.
- **Configuration**:
  - Temperature around 0.3–0.5 for stable rankings.
  - Max tokens set based on candidate list size.

### 5.2 Usage Pattern

- **Re-ranking and explanation**, not raw generation:
  - System always provides the full candidate list.
  - LLM is asked to:
    - Reorder within that constrained set.
    - Provide short, user-friendly explanations.
- **Single-call design**:
  - Prefer a single LLM call per recommendations request (ranking + explanations together).
- **Stateless**:
  - Each call is independent (no long-lived conversation state).

### 5.3 Prompt Design

- Prompt includes:
  - System message:
    - Role, constraints (no hallucinating new restaurants, use only provided candidates).
  - User preferences summary:
    - Location, budget, cuisines, rating threshold, occasion, notes.
  - Candidate list:
    - Compact JSON-like or bullet format with IDs and key fields.
  - Instructions:
    - Return JSON-like structure:
      - Ordered list of candidate IDs.
      - Per-ID explanation (≤ 2 sentences).
      - Optional global summary sentence.
- Backend:
  - Validates that the response:
    - Contains only known IDs.
    - Has reasonable length and structure.

### 5.4 Reliability & Fallbacks

- **Timeouts**:
  - Hard timeout (e.g., 1.5–2.0 seconds) on LLM call.
- **Retries**:
  - Limited retries (1–2) with exponential backoff for transient errors.
- **Circuit breaker**:
  - On repeated failures/timeouts, mark LLM as unavailable and:
    - Skip LLM ranking, return heuristic results with `llm_used = false`.
- **Feature flags**:
  - `USE_LLM_RANKING` per-environment.
  - `LLM_EXPLANATIONS_ONLY` mode (use heuristic for ordering, LLM just for text).

### 5.5 Cost & Token Management

- **Candidate truncation**:
  - Pre-rank and send only top N candidates to LLM (e.g., 20–50).
- **Text summarization**:
  - Avoid long review texts; optionally precompute short description fields offline.
- **Caching**:
  - Cache LLM responses based on:
    - Normalized preferences (location, cuisine set, budget band, rating).
    - Candidate set signature (IDs hash).
  - Use short TTL (e.g., minutes–hours) to avoid staleness while saving cost.

---

## 6. Scalability & Production Considerations

### 6.1 Performance & Scaling

- **Service scaling**
  - Stateless FastAPI pods/containers behind a load balancer.
  - Horizontal auto-scaling based on CPU and latency.
- **Data access**
  - For current dataset size (~50K rows), in-memory index is acceptable.
  - For future scaling:
    - Move to DB with indexing and query optimizations.
    - Possibly pre-materialized views for popular queries.
- **Concurrency**
  - Use async endpoints for LLM and I/O.
  - Tune worker count (e.g., Gunicorn + Uvicorn workers) based on CPU and expected concurrency.

### 6.2 Caching Strategy

- **Layer 1: Application cache**
  - In-memory LRU for:
    - `meta/filters` results.
    - Small, frequent recommendation queries.
- **Layer 2: Distributed cache (Redis)**
  - Cache:
    - Filtered candidate lists.
    - LLM results keyed by normalized preferences.
- **HTTP caching**
  - Recommendations endpoint is mostly user-specific, so minimal HTTP caching.
  - `meta/filters` can be cached with longer TTL.

### 6.3 Observability

- **Metrics**
  - Request-level:
    - `http_requests_total{endpoint,method,status}`
    - `http_request_duration_seconds_bucket{endpoint}`
  - Recommendation-specific:
    - `recommendations_candidates_count`
    - `recommendations_llm_used_total`
    - `recommendations_fallback_heuristic_total`
  - LLM-specific:
    - `llm_requests_total{status}`
    - `llm_tokens_in_total`, `llm_tokens_out_total`
    - `llm_latency_seconds_bucket`
- **Logging**
  - JSON logs with:
    - `request_id`, `user_agent`, `endpoint`, durations.
    - Errors with stack traces.
    - Redaction of any user free-text that could carry PII (if necessary).
- **Tracing**
  - Optional: OpenTelemetry traces across API, filtering, and LLM call spans.

### 6.4 Security

- **Secret management**
  - Groq API keys and DB credentials via environment variables or secret manager.
  - Never expose keys to frontend.
- **Transport security**
  - Enforce HTTPS end-to-end.
- **Rate limiting**
  - Basic per-IP rate limiting at gateway/load balancer level.
  - Optional API key for external consumers.
- **Input validation**
  - Pydantic models for strong validation and type checking.
  - Length and content limits on free-text fields (`notes`).
- **Hardening**
  - CORS configured to allow only trusted frontend origins.
  - OWASP best practices (no injection risk since no direct SQL from user inputs).

### 6.5 Configuration & Environments

- **Environments**
  - `dev`, `staging`, `prod` with different:
    - Dataset subsets (dev can use smaller sample).
    - LLM features (dev can disable LLM or use cheaper model).
- **Config**
  - Central configuration (e.g., `config.py` or env-based):
    - `DATASET_PATH`, `GROQ_API_KEY`, `USE_LLM_RANKING`, `MAX_RESULTS`, etc.

### 6.6 Testing Strategy

- **Unit tests**
  - Filtering and ranking correctness.
  - Dataset normalization edge cases.
  - Prompt formation logic.
- **Integration tests**
  - End-to-end recommendation flow with a test dataset.
  - Mocked LLM responses.
- **Performance tests**
  - Load tests for peak expected RPS.
  - Latency budget for `/recommendations` with and without LLM.
- **Smoke tests**
  - Lightweight checks on deployment:
    - `/health` endpoints.
    - One sample `/recommendations` call with known output shape.

