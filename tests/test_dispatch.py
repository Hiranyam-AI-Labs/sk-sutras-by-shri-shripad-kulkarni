"""Budget, usage and truthful metadata checks with no provider network calls."""

from types import SimpleNamespace
import json
import sqlite3

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
    assert "raw_usage" not in dispatcher.audit[0]


@pytest.mark.parametrize("outcome", ["SUCCESS", "INCOMPLETE", "FAILED"])
def test_reported_raw_usage_persists_without_changing_old_rows_or_reservations(tmp_path, outcome):
    """Persist real-shaped counters on new success/partial/failure records only.

    All responses are synthetic. Raw visible/thought/cache/official-total counts
    remain distinct, copied and JSON-safe; old audit bytes and reservations stay
    exact. This test performs no provider, credential or network operation.
    """
    path = tmp_path / "usage-audit.db"
    adapter = FakeAdapter()
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 2, audit_path=path)
    dispatcher.call("independent_validator", "legacy prompt")
    with sqlite3.connect(path) as db:
        original = db.execute("SELECT call_id,reservation_usd,status,record_json FROM council_dispatch_audit").fetchone()
    raw = {"prompt_token_count": 12, "candidates_token_count": 3, "thoughts_token_count": 97,
           "total_token_count": 112, "cached_content_token_count": 5,
           "cache_tokens_details": [{"modality": "TEXT", "token_count": 5}]}
    expected = json.loads(json.dumps(raw))
    def generate(prompt, system_prompt):
        """Emit one synthetic response with caller-owned raw metadata."""
        adapter.calls += 1
        return SimpleNamespace(content="partial" if outcome != "SUCCESS" else "complete",
            was_truncated=outcome != "SUCCESS", finish_reason="max_tokens" if outcome != "SUCCESS" else "stop",
            usage=SimpleNamespace(input_tokens=12, output_tokens=100, total_tokens=112,
                                  actual_cost_usd=None, raw_usage=raw))
    adapter.generate = generate
    if outcome == "FAILED":
        with pytest.raises(ValueError, match="incomplete"):
            dispatcher.call("independent_validator", "new prompt")
    else:
        dispatcher.call("independent_validator", "new prompt", allow_truncated=outcome == "INCOMPLETE")
    record = dispatcher.audit[-1]
    assert record["status"] == outcome and record["raw_usage"] == expected
    assert record["input_tokens"] == 12 and record["output_tokens"] == 100
    assert record["actual_cost_usd"] is None and adapter.calls == 2
    raw["thoughts_token_count"] = 0
    raw["cache_tokens_details"][0]["token_count"] = 0
    assert record["raw_usage"] == expected
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT call_id,reservation_usd,status,record_json FROM council_dispatch_audit ORDER BY rowid").fetchall()
    assert rows[0] == original
    assert rows[1][2] == outcome and json.loads(rows[1][3])["raw_usage"] == expected
    assert dispatcher.reserved_usd == pytest.approx(sum(row[1] for row in rows))
    resumed = BudgetedDispatcher(FakeRegistry(FakeAdapter()), RATES, 1, 2, audit_path=path)
    with pytest.raises(ValueError, match="budget"):
        resumed.call("independent_validator", "no retry")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT call_id,reservation_usd,status,record_json FROM council_dispatch_audit ORDER BY rowid").fetchall() == rows


@pytest.mark.parametrize("raw_usage", [None, {}])
def test_absent_or_empty_raw_usage_adds_no_audit_fields(raw_usage):
    """Legacy default response metadata remains byte-shape compatible."""
    adapter = FakeAdapter()
    original_generate = adapter.generate
    def generate(prompt, system_prompt):
        """Add only an absent/empty optional usage field to the old fake response."""
        response = original_generate(prompt, system_prompt)
        response.usage.raw_usage = raw_usage
        return response
    adapter.generate = generate
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 1)
    dispatcher.call("independent_validator", "prompt")
    assert "raw_usage" not in dispatcher.audit[0]


@pytest.mark.parametrize("raw_usage", [{"count": float("nan")}, {"count": object()}])
def test_non_json_usage_fails_once_without_fabrication(raw_usage):
    """Unsupported raw metadata cannot become a misleading serialized audit payload."""
    adapter = FakeAdapter()
    original_generate = adapter.generate
    def generate(prompt, system_prompt):
        """Return intentionally malformed metadata for the serialization guard."""
        response = original_generate(prompt, system_prompt)
        response.usage.raw_usage = raw_usage
        return response
    adapter.generate = generate
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 1)
    with pytest.raises((ValueError, TypeError)):
        dispatcher.call("independent_validator", "prompt")
    assert adapter.calls == 1 and dispatcher.audit[0]["status"] == "FAILED"
    assert "raw_usage" not in dispatcher.audit[0]
    assert dispatcher.reserved_usd > 0


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
    assert incomplete.audit[0]["usage_present"] is True
    assert incomplete.audit[0]["content_present"] is True
    assert incomplete.audit[0]["output_tokens"] == 2


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


def test_per_call_output_ceiling_is_reserved_and_restored():
    """A large composition ceiling changes its reservation and SDK limit only for one call."""
    adapter = FakeAdapter()
    observed = []
    original_generate = adapter.generate

    def capture_ceiling(prompt, system_prompt):
        observed.append(adapter.max_tokens)
        return original_generate(prompt, system_prompt)

    adapter.generate = capture_ceiling
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 2)
    dispatcher.call("independent_validator", "prompt", max_output_tokens=16000)
    assert observed == [16000]
    assert adapter.max_tokens == 100
    assert dispatcher.audit[0]["max_output_tokens"] == 16000
    assert dispatcher.audit[0]["estimated_reservation_usd"] > 0.16


def test_truncated_response_is_failed_with_usage_metadata():
    """A max-token response never becomes an accepted draft or a fabricated bill."""
    adapter = FakeAdapter()
    adapter.generate = lambda prompt, system_prompt: SimpleNamespace(
        content="partial", was_truncated=True, finish_reason="max_tokens",
        usage=SimpleNamespace(input_tokens=12, output_tokens=100,
                              total_tokens=112, actual_cost_usd=None))
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 1)
    with pytest.raises(ValueError, match="incomplete"):
        dispatcher.call("independent_validator", "prompt")
    record = dispatcher.audit[0]
    assert record["status"] == "FAILED"
    assert record["was_truncated"] is True
    assert record["finish_reason"] == "max_tokens"
    assert record["output_tokens"] == 100
    assert record["actual_cost_usd"] is None


def test_partial_composition_is_retained_but_never_success(tmp_path):
    """Recovery mode retains raw partial text with its separately reserved call."""
    import sqlite3
    adapter = FakeAdapter()
    adapter.generate = lambda prompt, system_prompt: SimpleNamespace(content='{"partial":', was_truncated=True,
        finish_reason="max_tokens", usage=SimpleNamespace(input_tokens=12, output_tokens=100, total_tokens=112, actual_cost_usd=None))
    dispatcher = BudgetedDispatcher(FakeRegistry(adapter), RATES, 1, 2, audit_path=tmp_path / "audit.db")
    assert dispatcher.call("independent_validator", "prompt", allow_truncated=True).was_truncated
    assert dispatcher.audit[0]["status"] == "INCOMPLETE"
    with sqlite3.connect(tmp_path / "audit.db") as db:
        assert db.execute("SELECT content FROM council_partial_outputs").fetchone()[0] == '{"partial":'
