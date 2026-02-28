from __future__ import annotations
import logging
import time
from typing import Any, Dict
from types import TracebackType

class StructuredLogger:
    def __init__(self, name: str = "app.service"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        """Logs an API request with structured fields."""
        log_data = {
            "type": "api_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "request_id": request_id,
        }
        if extra:
            log_data.update(extra)
        self.logger.info(f"Structured log: {log_data}")

    def log_error(
        self,
        message: str,
        error: Exception | None = None,
        request_id: str | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        """Logs an error with traceback if available."""
        log_data = {
            "type": "api_error",
            "message": message,
            "request_id": request_id,
            "error_type": type(error).__name__ if error else None,
        }
        if extra:
            log_data.update(extra)
        self.logger.error(f"Structured error: {log_data}")

service_logger = StructuredLogger()
