**AI Restaurant Recommendation Service**

An AI-powered restaurant recommendation engine that combines deterministic filtering, heuristic ranking, and LLM-based comparative reasoning to deliver structured, explainable results.

Built as part of the NextLeap Applied GenAI Bootcamp, this project demonstrates applied GenAI system design with production-oriented architecture and reliability guardrails.


**Product Overview**

This system addresses a common gap in AI-powered recommendations:
	•	Pure heuristic systems lack contextual reasoning
	•	Pure LLM systems lack reliability and control

This solution uses a hybrid architecture:
	1.	Deterministic filtering for correctness
	2.	Heuristic pre-ranking for efficiency
	3.	LLM re-ranking for contextual intelligence
	4.	Strict schema validation for stability

The LLM augments ranking decisions without compromising system control.


Key Capabilities
	•	Location-based filtering
	•	Cuisine matching
	•	Rating threshold enforcement
	•	Budget alignment
	•	Comparative LLM ranking
	•	Concise tradeoff-aware explanations
	•	Structured JSON output
	•	Fallback logic when LLM fails

Each recommendation includes:
	•	Rank
	•	LLM score
	•	Explanation (≤18 words)
	•	Smart badges (Top Pick, Highly Popular, Best Value, Top Rated)
	•	Summary insight


Architecture**

Frontend: React (Vite)
Backend: FastAPI
Data Layer: HuggingFace Zomato Dataset (Normalized)
Ranking: Heuristic Engine + Groq LLM
Validation: Pydantic + Strict JSON Parsing

Design principle: intelligence with constraints.


**API Example**

POST /api/v1/recommendations

{
  "location": "Banashankari",
  "cuisines": ["Chinese"],
  "min_rating": 4,
  "budget_min": 200,
  "budget_max": 1000,
  "max_results": 10,
  "use_llm": true
}

Response includes ranked restaurants, LLM explanations, scores, badges, and a summary.


**Engineering Decisions**

Why hybrid ranking?
	•	Reduces LLM cost
	•	Preserves deterministic correctness
	•	Improves reasoning quality
	•	Enables safe fallback

Why strict JSON output?
	•	Prevents hallucinations
	•	Ensures frontend stability
	•	Allows reliable parsing
	•	Protects ranking integrity


**Local Setup**

Backend:

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

Frontend:

cd frontend
npm install
npm run dev

Swagger UI:
Interactive API documentation is available locally via Swagger UI once the backend is running:

http://localhost:8000/docs

Production API documentation will be published after deployment.

**Deployment**

Cloud deployment is in progress.
A production deployment link will be added soon.


**Built As Part Of**

NextLeap Applied GenAI Bootcamp

**Author**

Nishita Kapkar


