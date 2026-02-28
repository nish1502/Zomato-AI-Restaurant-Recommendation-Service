from __future__ import annotations
import time
from enum import Enum
from typing import Callable, Any, TypeVar

# Generic return type for wrapped functions.
T = TypeVar("T")

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        name: str = "default_circuit",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        """
        Executes the function with circuit breaker logic.
        Returns None if the circuit is open.
        """
        self._update_state()

        if self.state == CircuitState.OPEN:
            # Circuit is open, skip execution.
            return None

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            return None

    async def acall(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any | None:
        """
        Executes the async function with circuit breaker logic.
        Returns None if the circuit is open.
        """
        self._update_state()

        if self.state == CircuitState.OPEN:
            return None

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            return None

    def _update_state(self) -> None:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout_seconds:
                self.state = CircuitState.HALF_OPEN

    def _on_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

groq_circuit_breaker = CircuitBreaker(name="groq_llm")
