from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Any

class DependencyStatus(BaseModel):
    status: str
    details: str | None = None

class ReadinessResponse(BaseModel):
    status: str
    dependencies: Dict[str, DependencyStatus]

def check_dataset_status() -> DependencyStatus:
    try:
        from app.services.dataset_loader import get_restaurants_index
        index = get_restaurants_index()
        if index is not None and not index.is_empty():
            return DependencyStatus(status="ok", details=f"Dataset loaded with {index.height} rows")
        return DependencyStatus(status="error", details="Dataset is empty or not loaded")
    except Exception as e:
        return DependencyStatus(status="error", details=str(e))

def check_groq_status() -> DependencyStatus:
    from app.core.config import settings
    if settings.GROQ_API_KEY:
        from app.phase4.circuit_breaker import groq_circuit_breaker
        return DependencyStatus(status=groq_circuit_breaker.state.value, details=f"Groq API Key present for model: {settings.GROQ_MODEL}")
    return DependencyStatus(status="warning", details="Groq API Key is missing")

def run_readiness_check() -> ReadinessResponse:
    dataset_status = check_dataset_status()
    groq_status = check_groq_status()
    
    total_status = "ready"
    if dataset_status.status == "error":
        total_status = "not_ready"
    
    return ReadinessResponse(
        status=total_status,
        dependencies={
            "dataset": dataset_status,
            "groq_llm": groq_status
        }
    )
