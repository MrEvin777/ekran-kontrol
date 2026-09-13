"""Circuit breaker for AI provider calls.

arkana_v2.py already has a working fallback chain (try provider N, on any
exception move to provider N+1, Ollama always last). What it lacked: a provider
that is currently down/rate-limited gets retried on *every single message*,
wasting the request's whole timeout on a hop that will fail again. This module
adds the missing piece -- after a few consecutive failures, skip that provider
for a cooldown window instead of paying its timeout again on the next message.

Kept as a separate file (not folded into arkana_v2.py) so it can be imported
and unit-tested without pulling in tkinter/pyautogui/pyaudio.
"""

from __future__ import annotations

import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_after_s: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after_s = reset_after_s
        self._state: dict[str, CircuitState] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def allow(self, provider_name: str) -> bool:
        state = self._state.get(provider_name, CircuitState.CLOSED)
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at.get(provider_name, 0) >= self.reset_after_s:
                self._state[provider_name] = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN: allow exactly one trial call through

    def record_success(self, provider_name: str) -> None:
        self._state[provider_name] = CircuitState.CLOSED
        self._consecutive_failures[provider_name] = 0

    def record_failure(self, provider_name: str) -> None:
        n = self._consecutive_failures.get(provider_name, 0) + 1
        self._consecutive_failures[provider_name] = n
        currently_half_open = self._state.get(provider_name) == CircuitState.HALF_OPEN
        if currently_half_open or n >= self.failure_threshold:
            self._state[provider_name] = CircuitState.OPEN
            self._opened_at[provider_name] = time.monotonic()

    def status(self) -> dict[str, str]:
        """For the 'Saglayici Durumu' panel: current state per provider."""
        return {name: state.value for name, state in self._state.items()}


class PerformanceMetrics:
    """Rolling per-provider call stats -- latency and success rate, kept in
    memory for the app's lifetime. Not persisted: this is a live-status view,
    not a billing/audit record (error_log.py already covers the audit trail)."""

    def __init__(self, window: int = 20) -> None:
        self.window = window
        self._latencies: dict[str, list[float]] = {}
        self._outcomes: dict[str, list[bool]] = {}

    def record(self, provider_name: str, latency_s: float, success: bool) -> None:
        lat = self._latencies.setdefault(provider_name, [])
        out = self._outcomes.setdefault(provider_name, [])
        lat.append(latency_s)
        out.append(success)
        del lat[: -self.window]
        del out[: -self.window]

    def summary(self) -> dict[str, dict]:
        result = {}
        for name, outcomes in self._outcomes.items():
            latencies = self._latencies.get(name, [])
            result[name] = {
                "calls": len(outcomes),
                "success_rate": round(sum(outcomes) / len(outcomes), 2) if outcomes else None,
                "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
            }
        return result


def call_with_retry(fn, max_attempts: int = 2, base_delay_s: float = 0.4):
    """Retries the SAME provider a couple of times with exponential backoff
    before giving up on it -- for a transient blip (one dropped connection),
    not for a provider that is actually down (the circuit breaker handles that
    one level up, across providers). Re-raises the last exception if every
    attempt fails, so the caller's own except/record_failure still fires."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(base_delay_s * (2**attempt))
    raise last_exc


# One shared breaker/metrics tracker for the whole app's lifetime (module-level
# singleton -- arkana_v2.py is itself a single-process, single-instance Tkinter
# app, so this matches its existing pattern of module-level state like CONFIG_DIR).
PROVIDER_BREAKER = ProviderCircuitBreaker()
PROVIDER_METRICS = PerformanceMetrics()
