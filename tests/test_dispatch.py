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


def test_reservation_survives_restart_and_blocks_repeat(tmp_path):
    """One completed call consumes the run cap after a fresh dispatcher instance."""
    path = tmp_path / "audit.db"
    first_adapter = FakeAdapter()
    first = BudgetedDispatcher(FakeRegistry(first_adapter), RATES, 1, 1,
                               audit_path=path, run_id="run-one")
    first.call("independent_validator", "prompt")
    restarted_adapter = FakeAdapter()
    restarted = BudgetedDispatcher(FakeRegistry(restarted_adapter), RATES, 1, 1,
                                   audit_path=path, run_id="run-one")
    with pytest.raises(ValueError):
        restarted.call("independent_validator", "prompt")
    assert restarted_adapter.calls == 0
    assert restarted.calls == 1


def test_nonfinite_prices_and_changed_run_config_fail_before_call(tmp_path):
    """Nonfinite rates and altered restart settings cannot bypass a cost cap."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, bad, 10)
        with pytest.raises(ValueError):
            BudgetedDispatcher(FakeRegistry(FakeAdapter()),
                               {"openai:gpt-4o": {**RATES["openai:gpt-4o"], "input": bad}}, 1, 10)
    path = tmp_path / "run.db"
    BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 1, 10,
                       audit_path=path, run_id="fixed")
    with pytest.raises(ValueError, match="configuration changed"):
        BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 2, 10,
                           audit_path=path, run_id="fixed")


def test_role_model_stays_frozen_across_restart(tmp_path):
    """One run ID cannot substitute a new model after preflight."""
    path = tmp_path / "roles.db"
    first = BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 1, 10,
                               audit_path=path, run_id="fixed")
    first.preflight_roles(["independent_validator"])
    changed = FakeAdapter()
    changed.model_id = "different"
    restarted = BudgetedDispatcher(FakeRegistry(changed), RATES, 1, 10,
                                   audit_path=path, run_id="fixed")
    with pytest.raises(ValueError, match="Durable role model"):
        restarted.preflight_roles(["independent_validator"])


def test_role_timeout_is_clamped_to_run_deadline_and_restored():
    """A configured long role timeout cannot outlive the run window."""
    adapter = FakeAdapter()
    adapter.timeout_seconds = 60.0
    observed = []
    original_generate = adapter.generate

    def capture_timeout(prompt, system_prompt):
        observed.append(adapter.timeout_seconds)
        return original_generate(prompt, system_prompt)

    adapter.generate = capture_timeout
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 2,
                                    max_elapsed_seconds=10,
                                    role_timeouts={"independent_validator": 120.0})
    dispatcher.call("independent_validator", "prompt")
    assert 0 < observed[0] <= 10
    assert adapter.timeout_seconds == 60.0
    assert dispatcher.audit[0]["effective_timeout_seconds"] == observed[0]


def test_invalid_role_timeout_fails_before_call():
    """NaN, infinity and nonpositive timeout settings cannot reach an SDK."""
    for value in (float("nan"), float("inf"), 0, -1):
        with pytest.raises(ValueError, match="Role timeouts"):
            BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 1, 1,
                               role_timeouts={"independent_validator": value})
