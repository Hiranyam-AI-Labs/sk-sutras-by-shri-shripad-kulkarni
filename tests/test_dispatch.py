"""Budget, usage and truthful metadata checks with no provider network calls."""

from types import SimpleNamespace

import pytest

from src.providers.dispatch import BudgetedDispatcher

RATES = {"openai:gpt-4o": {"input": 2.5, "output": 10,
                            "effective_date": "2026-11-13"}}


class FakeAdapter:
    """Minimal configured adapter that counts attempted calls."""
    provider_name, model_id, max_tokens = "openai", "gpt-4o", 100

    def __init__(self, usage=5):
        """Set response token count; zero simulates unavailable usage."""
        self.usage, self.calls = usage, 0

    def estimate_tokens(self, text):
        """Return bounded synthetic input token count for budget tests."""
        return 10

    def generate(self, prompt, system_prompt):
        """Return a mocked successful response without HTTP or actual billing claims."""
        self.calls += 1
        return SimpleNamespace(content="draft", was_truncated=False, finish_reason="stop",
                               usage=SimpleNamespace(input_tokens=3, output_tokens=2,
                                                     total_tokens=self.usage, actual_cost_usd=None))


class FakeRegistry:
    """Expose one frozen role adapter for dispatch tests."""

    def __init__(self, adapter):
        """Store the test adapter without side effects."""
        self.adapter = adapter

    def get_adapter(self, role):
        """Resolve one known role or fail explicitly."""
        if role != "independent_validator":
            raise ValueError("Unknown role")
        return self.adapter


def test_success_does_not_fabricate_http_or_actual_cost():
    """A response hash proves content identity only; billing/status remain unknown."""
    dispatcher = BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 1, 1)
    dispatcher.call("independent_validator", "prompt")
    assert dispatcher.audit[0]["http_status"] is None
    assert dispatcher.audit[0]["actual_cost_usd"] is None
    assert dispatcher.audit[0]["status"] == "SUCCESS"


def test_budget_and_missing_usage_fail_closed():
    """Pre-call budget blocks invocation, and missing usage is not success."""
    adapter = FakeAdapter()
    blocked = BudgetedDispatcher(FakeRegistry(adapter), RATES, .00001, 1)
    with pytest.raises(ValueError):
        blocked.call("independent_validator", "prompt")
    assert adapter.calls == 0
    incomplete = BudgetedDispatcher(FakeRegistry(FakeAdapter(0)), RATES, 1, 1)
    with pytest.raises(ValueError):
        incomplete.call("independent_validator", "prompt")
    assert incomplete.audit[0]["status"] == "FAILED"
