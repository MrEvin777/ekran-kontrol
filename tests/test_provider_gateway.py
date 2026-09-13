import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from provider_gateway import CircuitState, ProviderCircuitBreaker  # noqa: E402


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
