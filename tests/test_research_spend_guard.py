"""Real dispatcher/SQLite guard tests with fake adapters and no credential imports."""

import ast
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import threading
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
RATES = {"anthropic:claude-sonnet-5-5": {"input": 2., "output": 10., "effective_date": "2026-11-18"},
         "openai:gpt-4o": {"input": 2.5, "output": 10., "effective_date": "2026-11-18"}}
PER_CALL = 0.0012


class Adapter:
    """Inert adapter with deterministic projection and counted fake generations."""

    def __init__(self, provider="anthropic"):
        """Set frozen provider metadata without credentials or SDK construction."""
        self.provider_name = provider
        self.model_id = "claude-sonnet-5-5" if provider == "anthropic" else "gpt-4o"
        self.max_tokens, self.timeout_seconds = 100, 2
        self.calls = 0
        self.failure = False
        self.truncated = False

    def estimate_tokens(self, text):
        """Return a fixed input estimate for exact-boundary budget tests."""
        return 100

    def generate(self, **kwargs):
        """Count one fake request, optionally fail, otherwise expose valid usage."""
        self.calls += 1
        if self.failure:
            raise RuntimeError("Simulated insufficient Claude credit")
        return SimpleNamespace(content='{"partial":' if self.truncated else "{}",
                               was_truncated=self.truncated,
                               finish_reason="max_tokens" if self.truncated else "stop",
                               usage=SimpleNamespace(total_tokens=2, input_tokens=1, output_tokens=1,
                                                     actual_cost_usd=None))


@pytest.fixture
def environment(tmp_path, monkeypatch):
    """Load real guard/dispatcher source without provider package startup."""
    spec = importlib.util.spec_from_file_location("_offline_spend_guard",
                                                 ROOT / "src/providers/research_spend_guard.py")
    guard_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, guard_module)
    spec.loader.exec_module(guard_module)
    filename = ROOT / "src/providers/dispatch.py"
    tree = ast.parse(filename.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module == "src.providers.registry")]
    namespace = {"ProviderRegistry": object}
    exec(compile(tree, str(filename), "exec"), namespace)
    adapters = {"researcher": Adapter(), "sutrakar": Adapter(), "validator": Adapter("openai")}
    registry = SimpleNamespace(get_adapter=lambda role: adapters[role])
    path = tmp_path / "dispatch.db"

    def dispatcher(run_id="one"):
        """Create a real audited dispatcher around inert adapters."""
        return namespace["BudgetedDispatcher"](registry, RATES, 100., 100, path, run_id, 60)

    return SimpleNamespace(module=guard_module, path=path, dispatcher=dispatcher, adapters=adapters)


def test_exact_cap_and_all_run_ids_share_history(environment):
    """Two calls fit exactly; a fresh run/guard instance cannot buy a third."""
    env = environment
    guard = env.module.ResearchSpendGuard(env.path, 2 * PER_CALL, "pilot")
    guard.call(env.dispatcher("one"), "researcher", "prompt", "system", 100)
    resumed = env.module.ResearchSpendGuard(env.path, 2 * PER_CALL, "pilot")
    resumed.call(env.dispatcher("two"), "sutrakar", "prompt", "system", 100)
    assert resumed.reserved_usd == pytest.approx(2 * PER_CALL)
    with pytest.raises(env.module.ResearchSpendLimitExceeded, match="before provider call"):
        resumed.call(env.dispatcher("three"), "sutrakar", "prompt", "system", 100)
    assert sum(a.calls for a in env.adapters.values()) == 2


@pytest.mark.parametrize("allow_truncated", [False, True])
def test_failed_call_stays_reserved_and_never_retries(environment, allow_truncated):
    """A provider error consumes one reservation and propagates immediately."""
    env = environment
    guard = env.module.ResearchSpendGuard(env.path, PER_CALL)
    env.adapters["sutrakar"].failure = True
    with pytest.raises(RuntimeError, match="insufficient Claude credit"):
        guard.call(env.dispatcher(), "sutrakar", "prompt", "system", 100,
                   allow_truncated=allow_truncated)
    assert env.adapters["sutrakar"].calls == 1
    assert guard.reserved_usd == pytest.approx(PER_CALL)
    with pytest.raises(env.module.ResearchProviderStopped):
        guard.call(env.dispatcher("new-run"), "researcher", "prompt", "system", 100)
    assert env.adapters["researcher"].calls == 0
    with sqlite3.connect(env.path) as db:
        assert db.execute("SELECT status FROM council_dispatch_audit").fetchall() == [("FAILED",)]


def test_cap_exception_is_terminal_for_council(environment):
    """The council must not classify budget exhaustion as a schema-repair failure."""
    error = environment.module.ResearchSpendLimitExceeded("cap reached")
    assert isinstance(error, RuntimeError)
    assert not isinstance(error, ValueError)


def test_queued_claude_role_stops_after_failure_even_with_budget_remaining(environment):
    """Concurrent guards spend at most one failed request, not one per Claude role."""
    env = environment
    guards = [env.module.ResearchSpendGuard(env.path, 1.5, name) for name in ("a", "b")]
    dispatchers = [env.dispatcher(name) for name in ("a", "b")]
    env.adapters["researcher"].failure = env.adapters["sutrakar"].failure = True
    start = threading.Barrier(2)

    def call(index):
        """Queue both roles; identify original failure versus the latched stop."""
        start.wait(timeout=3)
        try:
            guards[index].call(dispatchers[index], ("researcher", "sutrakar")[index], "p", "s", 100)
        except env.module.ResearchProviderStopped:
            return "latched"
        except RuntimeError:
            return "provider failed"
        pytest.fail("A failing provider must not return success")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(call, (0, 1))) == ["latched", "provider failed"]
    assert env.adapters["researcher"].calls + env.adapters["sutrakar"].calls == 1
    assert guards[0].reserved_usd == pytest.approx(PER_CALL)


def test_guard_id_freezes_cap_durably(environment):
    """Reopening the same ID preserves its ceiling; higher or lower caps fail."""
    env = environment
    env.module.ResearchSpendGuard(env.path, 1.5, "pilot")
    for changed in (1., 2.):
        with pytest.raises(ValueError, match="Frozen"):
            env.module.ResearchSpendGuard(env.path, changed, "pilot")
    assert env.module.ResearchSpendGuard(env.path, 1.5, "pilot").reserved_usd == 0


def test_prior_started_and_failed_reservations_count_other_providers_do_not(environment):
    """Count history from before the guard across statuses, without OpenAI cost."""
    env = environment
    dispatcher = env.dispatcher()
    with sqlite3.connect(env.path) as db:
        for number, (provider, status) in enumerate([
                ("anthropic", "STARTED"), ("anthropic", "FAILED"),
                ("anthropic", "INCOMPLETE"), ("openai", "SUCCESS")]):
            db.execute("INSERT INTO council_dispatch_audit VALUES (?,?,?,?,?)",
                       (str(number), "previous", PER_CALL, status, json.dumps({"provider": provider})))
    guard = env.module.ResearchSpendGuard(env.path, 3 * PER_CALL)
    assert guard.reserved_usd == pytest.approx(3 * PER_CALL)
    with pytest.raises(env.module.ResearchSpendLimitExceeded):
        guard.call(dispatcher, "researcher", "prompt", "system", 100)
    guard.call(dispatcher, "validator", "prompt", "system", 100)
    assert env.adapters["validator"].calls == 1
    assert guard.reserved_usd == pytest.approx(3 * PER_CALL)


def test_shared_process_lock_across_guard_instances_and_roles(environment):
    """Two concurrent roles cannot both spend the last single-call allowance."""
    env = environment
    guards = [env.module.ResearchSpendGuard(env.path, PER_CALL, name) for name in ("a", "b")]
    dispatchers = [env.dispatcher(name) for name in ("a", "b")]
    start = threading.Barrier(2)

    def call(index):
        """Compete for one durable reservation through separate guard instances."""
        start.wait(timeout=3)
        try:
            guards[index].call(dispatchers[index], ("researcher", "sutrakar")[index], "p", "s", 100)
            return "called"
        except env.module.ResearchSpendLimitExceeded:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(call, (0, 1))) == ["blocked", "called"]
    assert env.adapters["researcher"].calls + env.adapters["sutrakar"].calls == 1


def test_output_ceiling_reserved_without_model_or_rate_changes(environment):
    """Use the exact explicit ceiling, leaving binding/rates untouched."""
    env = environment
    dispatcher = env.dispatcher()
    guard = env.module.ResearchSpendGuard(env.path, PER_CALL)
    with pytest.raises(env.module.ResearchSpendLimitExceeded):
        guard.call(dispatcher, "sutrakar", "prompt", "system", 200)
    assert env.adapters["sutrakar"].calls == 0
    assert env.adapters["sutrakar"].max_tokens == 100
    assert env.adapters["sutrakar"].model_id == "claude-sonnet-5-5"
    assert dispatcher.rates == RATES


def test_replaced_registry_cannot_bypass_cached_claude_cap(environment):
    """A role switched to OpenAI cannot hide a cached Anthropic dispatcher adapter."""
    env = environment
    dispatcher = env.dispatcher()
    guard = env.module.ResearchSpendGuard(env.path, PER_CALL)
    guard.call(dispatcher, "sutrakar", "p", "s", 100)
    previous = env.adapters["sutrakar"]
    env.adapters["sutrakar"] = Adapter("openai")
    with pytest.raises(ValueError, match="adapter changed"):
        guard.call(dispatcher, "sutrakar", "p", "s", 100)
    assert previous.calls == 1
    assert env.adapters["sutrakar"].calls == 0


def test_wrong_or_nondurable_dispatcher_path_fails(environment, tmp_path):
    """The cap cannot be checked against one database while spending in another."""
    env = environment
    guard = env.module.ResearchSpendGuard(env.path, 1.5)
    dispatcher = env.dispatcher()
    for path in (None, tmp_path / "different.db"):
        dispatcher.audit_path = path
        with pytest.raises(ValueError, match="same durable"):
            guard.call(dispatcher, "sutrakar", "p", "s", 100)
    assert env.adapters["sutrakar"].calls == 0


@pytest.mark.parametrize("cap", [0, -1, float("nan"), float("inf"), True, "1.5"])
def test_invalid_cap_rejected_before_dispatch(environment, cap):
    """Reject nonfinite, boolean and nonnumeric ceilings without generation."""
    with pytest.raises(ValueError, match="positive and finite"):
        environment.module.ResearchSpendGuard(environment.path, cap)


@pytest.mark.parametrize("raw", ["broken JSON", "{}", '{"provider": null}'])
def test_corrupt_audit_fails_closed(environment, raw):
    """Unknown historical spend cannot be treated as zero allowance consumed."""
    env = environment
    dispatcher = env.dispatcher()
    guard = env.module.ResearchSpendGuard(env.path, 1.5)
    with sqlite3.connect(env.path) as db:
        db.execute("INSERT INTO council_dispatch_audit VALUES ('bad','old',1,'FAILED',?)", (raw,))
    with pytest.raises(ValueError, match="audit|metadata"):
        guard.call(dispatcher, "sutrakar", "p", "s", 100)
    assert env.adapters["sutrakar"].calls == 0


@pytest.mark.parametrize("role", ["sutrakar", "validator"])
def test_allow_truncated_passthrough_keeps_partial_and_latches_only_claude(environment, role):
    """Persist partial SDK text, then block future Claude calls without losing it."""
    env = environment
    dispatcher = env.dispatcher()
    guard = env.module.ResearchSpendGuard(env.path, 1.5)
    adapter = env.adapters[role]
    adapter.truncated = True
    response = guard.call(dispatcher, role, "p", "s", 100, allow_truncated=True)
    assert response.content == '{"partial":'
    assert response.was_truncated is True
    assert adapter.calls == 1
    with sqlite3.connect(env.path) as db:
        record = db.execute("SELECT status,reservation_usd FROM council_dispatch_audit").fetchone()
        assert record[0] == "INCOMPLETE" and record[1] > 0
        assert db.execute("SELECT content FROM council_partial_outputs").fetchall() == [(response.content,)]
    if role == "sutrakar":
        assert guard.reserved_usd == pytest.approx(PER_CALL)
        resumed = env.module.ResearchSpendGuard(env.path, 1.5, "second-guard")
        with pytest.raises(env.module.ResearchProviderStopped, match="TruncatedProviderResponse"):
            resumed.call(env.dispatcher("second-run"), "researcher", "p", "s", 100,
                         allow_truncated=True)
        assert env.adapters["researcher"].calls == 0
        assert adapter.calls == 1
        return
    # An OpenAI partial does not latch the Claude-specific guard. The parent
    # remains responsible for its overall stop after saving this response.
    adapter.truncated = False
    assert guard.call(dispatcher, role, "p", "s", 100).was_truncated is False
    assert adapter.calls == 2


def test_truncated_claude_response_blocks_queued_other_role(environment):
    """Serialize two roles: return one partial and block the other before dispatch."""
    env = environment
    guards = [env.module.ResearchSpendGuard(env.path, 1.5, name) for name in ("a", "b")]
    dispatchers = [env.dispatcher(name) for name in ("a", "b")]
    env.adapters["researcher"].truncated = env.adapters["sutrakar"].truncated = True
    start = threading.Barrier(2)

    def call(index):
        """Race both Claude roles through the shared lock with partial capture enabled."""
        start.wait(timeout=3)
        try:
            response = guards[index].call(dispatchers[index], ("researcher", "sutrakar")[index],
                                          "p", "s", 100, allow_truncated=True)
            assert response.was_truncated and response.content == '{"partial":'
            return "partial returned"
        except env.module.ResearchProviderStopped:
            return "queued role blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(call, (0, 1))) == ["partial returned", "queued role blocked"]
    assert env.adapters["researcher"].calls + env.adapters["sutrakar"].calls == 1
    with sqlite3.connect(env.path) as db:
        assert db.execute("SELECT status FROM council_dispatch_audit").fetchall() == [("INCOMPLETE",)]
        assert db.execute("SELECT content FROM council_partial_outputs").fetchall() == [('{"partial":',)]


@pytest.mark.parametrize("role", ["sutrakar", "validator"])
def test_default_still_rejects_truncation_without_automatic_retry(environment, role):
    """The new option is opt-in; default incomplete responses remain audited failures."""
    env = environment
    dispatcher = env.dispatcher()
    guard = env.module.ResearchSpendGuard(env.path, 1.5)
    env.adapters[role].truncated = True
    with pytest.raises(ValueError, match="incomplete"):
        guard.call(dispatcher, role, "p", "s", 100)
    assert env.adapters[role].calls == 1
    with sqlite3.connect(env.path) as db:
        assert db.execute("SELECT status FROM council_dispatch_audit").fetchall() == [("FAILED",)]
