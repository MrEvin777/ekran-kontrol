import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from provider_gateway import (  # noqa: E402
    CircuitState,
    PerformanceMetrics,
    ProviderCircuitBreaker,
    call_with_retry,
)


def test_allows_calls_when_closed():
    b = ProviderCircuitBreaker()
    assert b.allow("groq")


def test_opens_after_threshold_consecutive_failures():
    b = ProviderCircuitBreaker(failure_threshold=3, reset_after_s=60)
    b.record_failure("groq")
    b.record_failure("groq")
    assert b.allow("groq")  # 2 failures, still closed
    b.record_failure("groq")
    assert not b.allow("groq")  # 3rd failure trips it


def test_success_resets_failure_count():
    b = ProviderCircuitBreaker(failure_threshold=3, reset_after_s=60)
    b.record_failure("groq")
    b.record_failure("groq")
    b.record_success("groq")
    b.record_failure("groq")
    assert b.allow("groq")  # only 1 failure since the reset


def test_reopens_after_cooldown_then_recloses_on_success():
    b = ProviderCircuitBreaker(failure_threshold=1, reset_after_s=0.05)
    b.record_failure("groq")
    assert not b.allow("groq")
    time.sleep(0.1)
    assert b.allow("groq")  # cooldown elapsed -> half-open trial allowed
    b.record_success("groq")
    assert b.status()["groq"] == CircuitState.CLOSED.value


def test_a_failure_during_half_open_reopens_immediately():
    b = ProviderCircuitBreaker(failure_threshold=5, reset_after_s=0.05)
    b.record_failure("groq")  # below threshold, stays closed
    assert b.allow("groq")
    b._state["groq"] = CircuitState.HALF_OPEN  # simulate cooldown having elapsed
    b.record_failure("groq")
    assert not b.allow("groq")  # one failure in half-open is enough to reopen


def test_providers_are_independent():
    b = ProviderCircuitBreaker(failure_threshold=1, reset_after_s=60)
    b.record_failure("groq")
    assert not b.allow("groq")
    assert b.allow("cerebras")  # a different provider's breaker is untouched


def test_call_with_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("blip")
        return "ok"

    result = call_with_retry(flaky, max_attempts=3, base_delay_s=0.01)
    assert result == "ok"
    assert calls["n"] == 2


def test_call_with_retry_raises_after_exhausting_attempts():
    def always_fails():
        raise TimeoutError("dead")

    with pytest.raises(TimeoutError):
        call_with_retry(always_fails, max_attempts=2, base_delay_s=0.01)


def test_call_with_retry_does_not_retry_a_call_that_succeeds_first_try():
    calls = {"n": 0}

    def works():
        calls["n"] += 1
        return "ok"

    call_with_retry(works, max_attempts=5, base_delay_s=0.01)
    assert calls["n"] == 1


def test_performance_metrics_summary():
    m = PerformanceMetrics(window=10)
    m.record("groq", 0.5, True)
    m.record("groq", 1.5, True)
    m.record("groq", 2.0, False)
    summary = m.summary()
    assert summary["groq"]["calls"] == 3
    assert summary["groq"]["success_rate"] == round(2 / 3, 2)
    assert summary["groq"]["avg_latency_s"] == round((0.5 + 1.5 + 2.0) / 3, 2)


def test_performance_metrics_rolling_window_drops_oldest():
    m = PerformanceMetrics(window=2)
    m.record("groq", 1.0, True)
    m.record("groq", 2.0, True)
    m.record("groq", 3.0, False)  # window=2 -> the first record (1.0) is dropped
    summary = m.summary()
    assert summary["groq"]["calls"] == 2
    assert summary["groq"]["avg_latency_s"] == 2.5
