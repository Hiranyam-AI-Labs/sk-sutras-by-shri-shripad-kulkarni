"""Offline transport tests: fake adapters only, no credentials or network calls.

These tests establish durable accounting/JSON boundaries, NOT semantic quality,
scholarly validation, live connectivity, actual billing or author approval.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from src.orchestration import source_first_provider as boundary
from scripts import run_research_book as runner


SOURCES = {"narada": "a" * 64, "shandilya": "b" * 64}
PAYLOAD = {"sources": [{"id": "N23", "text": "भक्ती"}], "instruction": "compare"}
SECRET = "fake-credential-never-log"


class FakeAdapter:
    """Count attempts and expose synthetic provider metadata without an SDK."""

    def __init__(self, voice):
        """Bind one exact frozen role; fake responses carry no actual bill."""
        self.provider_name = runner.PROVIDERS[voice]
        self.model_id = runner.MODELS[voice][1]
        self.max_tokens = 100
        self.offline_mode = True
        self.timeout_seconds = 60
        self.calls = 0
        self.content = '{"answer_mr":"प्रेम","items":[1,2]}'
        self.truncated = False
        self.error = None
        self.response_model = self.model_id
        self.response_provider = self.provider_name
        self.total_tokens = 15
        self.entered = None
        self.release = None
        self.observed = []

    def estimate_tokens(self, text):
        """Return a fixed fake estimate for deterministic reservation checks."""
        return 10

    def generate(self, prompt, system_prompt):
        """Make one synthetic attempt, optionally failing/blocking/truncating."""
        self.calls += 1
        self.observed.append((prompt, system_prompt, self.max_tokens))
        if self.entered:
            self.entered.set()
            assert self.release.wait(5)
        if self.error:
            raise self.error
        return SimpleNamespace(
            content=self.content, provider=self.response_provider, model_id=self.response_model,
            was_truncated=self.truncated, finish_reason="max_tokens" if self.truncated else "stop",
            usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                  total_tokens=self.total_tokens, actual_cost_usd=None))


class FakeRegistry:
    """Return exact fake role allocations; never construct credential readers."""

    def __init__(self):
        """Initialize all five independently mutable fake adapters."""
        self.adapters = {role: FakeAdapter(voice) for voice, (role, _) in runner.MODELS.items()}

    def get_adapter(self, role):
        """Resolve a role, letting invalid caller mappings fail explicitly."""
        return self.adapters[role]


@pytest.fixture(autouse=True)
def prohibit_credentials_and_real_registry(monkeypatch):
    """Every test fails if production credentials or adapter construction occurs."""
    def forbidden(*args, **kwargs):
        """Tripwire: tests may not load keys or instantiate real adapters."""
        pytest.fail("Real credentials/registry forbidden in offline tests")

    monkeypatch.setattr(runner, "load_project_credentials", forbidden)
    monkeypatch.setattr("src.providers.registry.ProviderRegistry", forbidden)


def make(path, registry=None, **options):
    """Build a boundary with small explicit synthetic run budgets."""
    return boundary.SourceFirstProvider(
        path, registry or FakeRegistry(),
        **{"source_hashes": SOURCES, "max_usd": 1, "max_calls": 20,
           "claude_cap_usd": .5, **options})


def invoke(client, voice="researcher", stage="batch-001/research", **options):
    """Call one stable slot using the public five-argument interface."""
    return client(voice, stage, options.get("system", "Return JSON."),
                  options.get("payload", PAYLOAD), options.get("max_output_tokens", 100))


# Verify only fixed diagnostic enums survive exception classification; original
# credential-like message text must never become a logged error description.
@pytest.mark.parametrize('error,code', [
    (TimeoutError(SECRET), 'TIMEOUT'),
    (RuntimeError('credit balance is too low ' + SECRET), 'CREDIT_BALANCE_LOW'),
    (RuntimeError('Streaming is required ' + SECRET), 'SDK_STREAMING_REQUIRED'),
    (RuntimeError(SECRET), 'UNCLASSIFIED_PROVIDER_FAILURE'),
])
def test_sanitized_failure_codes(error, code):
    assert boundary.failure_code(error) == code


# Verify a single explicit correction preserves the original failed reservation,
# can resume once, and cannot be chained into automatic retries. Fake guard state
# is reset to simulate the fresh process required by the documented recovery.
def test_single_diagnosed_timeout_correction_preserves_failure_and_cost(tmp_path, monkeypatch):
    path = tmp_path / 'recover'
    registry = FakeRegistry()
    first = make(path, registry)
    registry.adapters[runner.MODELS['researcher'][0]].error = TimeoutError('request timed out')
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(first)
    before = first.dispatcher.reserved_usd
    with sqlite3.connect(path / 'boundary.db') as db:
        failed_hash = db.execute('SELECT request_sha256 FROM calls').fetchone()[0]
    from src.providers import research_spend_guard
    monkeypatch.setattr(research_spend_guard, '_FAILURES', {})
    resumed = make(path, resume=True)
    resumed.authorize_timeout_correction('researcher', 'batch-001/research',
        'batch-001/research-corrected', failed_hash, 'd' * 64)
    assert resumed.resolve_stage('researcher', 'batch-001/research') == 'batch-001/research-corrected'
    result = invoke(resumed, stage=resumed.resolve_stage('researcher', 'batch-001/research'))
    assert result['answer_mr'] == 'प्रेम'
    assert resumed.dispatcher.reserved_usd > before
    assert sorted(states(path)) == ['HARD_FAILED', 'SUCCESS']
    calls = resumed.dispatcher.calls
    assert invoke(resumed, stage='batch-001/research-corrected') == result
    assert resumed.dispatcher.calls == calls
    with pytest.raises(ValueError):
        resumed.authorize_timeout_correction('researcher', 'batch-001/research',
            'another-correction', failed_hash, 'e' * 64)


# Verify absent/mismatched evidence cannot authorize an unpaid-style retry of a
# prior source slot; no source, result, reservation or status is rewritten.
def test_timeout_correction_requires_exact_failed_request(tmp_path):
    client = make(tmp_path / 'no-failure')
    with pytest.raises(ValueError):
        client.authorize_timeout_correction('researcher', 'batch-001/research',
            'new-stage', 'a' * 64, 'd' * 64)
    assert client.dispatcher.calls == 0


# Verify known credit failures, unknown new failures and saved partial output
# cannot be relabelled as a timeout to unlock another paid attempt.
@pytest.mark.parametrize('kind', ['credit', 'unknown', 'partial'])
def test_timeout_correction_rejects_ineligible_failures(tmp_path, kind):
    path = tmp_path / kind
    registry = FakeRegistry()
    client = make(path, registry)
    adapter = registry.adapters[runner.MODELS['researcher'][0]]
    if kind == 'partial':
        adapter.truncated = True
    else:
        adapter.error = RuntimeError('credit balance is too low' if kind == 'credit' else SECRET)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    with sqlite3.connect(path / 'boundary.db') as db:
        failed_hash = db.execute('SELECT request_sha256 FROM calls').fetchone()[0]
    with pytest.raises(ValueError):
        client.authorize_timeout_correction('researcher', 'batch-001/research',
            'corrected', failed_hash, 'd' * 64)
    assert client.dispatcher.calls == 1


# Create one synthetic timeout and simulate a fresh process for explicit repair.
# Return the resumed boundary and exact failed identities; no real SDK is used.
def recoverable_fixture(path, monkeypatch):
    registry = FakeRegistry()
    client = make(path, registry)
    registry.adapters[runner.MODELS['researcher'][0]].error = TimeoutError('timed out')
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    with sqlite3.connect(path / 'boundary.db') as db:
        slot, request = db.execute('SELECT slot,request_sha256 FROM calls').fetchone()
    from src.providers import research_spend_guard
    monkeypatch.setattr(research_spend_guard, '_FAILURES', {})
    return make(path, resume=True), slot, request


# Verify timeout correction cannot pay for altered meaning, instructions or
# output limits merely by changing the replacement stage's first request.
@pytest.mark.parametrize('change', ['payload', 'system', 'max_output_tokens'])
def test_recovery_rejects_changed_original_request_before_spending(tmp_path, monkeypatch, change):
    client, slot, request = recoverable_fixture(tmp_path / change, monkeypatch)
    client.authorize_timeout_correction('researcher', 'batch-001/research', 'corrected', request, 'd' * 64)
    options = {'payload': {'different': True}} if change == 'payload' else (
        {'system': 'Different task'} if change == 'system' else {'max_output_tokens': 101})
    before = client.dispatcher.reserved_usd
    with pytest.raises(ValueError, match='exact original request'):
        invoke(client, stage='corrected', **options)
    assert client.dispatcher.calls == 1 and client.dispatcher.reserved_usd == before


# Verify saved response bytes defeat a misleading null database raw hash.
# Both boundary files and dispatcher partial storage are checked, never deleted.
@pytest.mark.parametrize('storage', ['txt', 'tmp', 'dispatcher'])
def test_recovery_rejects_saved_output_even_with_null_database_hash(tmp_path, monkeypatch, storage):
    path = tmp_path / storage
    client, slot, request = recoverable_fixture(path, monkeypatch)
    if storage == 'dispatcher':
        with sqlite3.connect(path / 'dispatch.db') as db:
            call = db.execute('SELECT call_id FROM council_dispatch_audit').fetchone()[0]
            db.execute('CREATE TABLE council_partial_outputs (call_id TEXT PRIMARY KEY,run_id TEXT,content TEXT)')
            db.execute('INSERT INTO council_partial_outputs VALUES (?,?,?)', (call, 'source-first', 'partial'))
    else:
        (path / 'raw' / (slot + '.' + storage)).write_text('partial')
    with sqlite3.connect(path / 'boundary.db') as db:
        db.execute("UPDATE calls SET error_type='DispatchOrResponseFailure'")
    with pytest.raises(ValueError):
        client.authorize_timeout_correction('researcher', 'batch-001/research', 'corrected', request, 'd' * 64)
    assert client.dispatcher.calls == 1


# Verify eligibility is rechecked at actual dispatch, not only authorization.
@pytest.mark.parametrize('change', ['failure_row', 'saved_output'])
def test_recovery_rechecks_failed_state_before_attempt(tmp_path, monkeypatch, change):
    path = tmp_path / change
    client, slot, request = recoverable_fixture(path, monkeypatch)
    client.authorize_timeout_correction('researcher', 'batch-001/research', 'corrected', request, 'd' * 64)
    if change == 'failure_row':
        with sqlite3.connect(path / 'boundary.db') as db:
            db.execute("UPDATE calls SET error_type='CREDIT_BALANCE_LOW' WHERE slot=?", (slot,))
    else:
        (path / 'raw' / (slot + '.tmp')).write_text('partial')
    with pytest.raises(ValueError):
        invoke(client, stage='corrected')
    assert client.dispatcher.calls == 1


# Verify a complete paid response lost before raw-file persistence is not treated
# as a no-response timeout, even if an older generic error label hid that fact.
def test_recovery_rejects_unmatched_dispatch_success_after_raw_save_failure(tmp_path, monkeypatch):
    path = tmp_path / 'lost-complete-response'
    client = make(path)

    def fail_save(*args):
        """Simulate a disk failure before any raw file is created."""
        raise OSError('synthetic storage failure')

    monkeypatch.setattr(client, '_raw', fail_save)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    with sqlite3.connect(path / 'boundary.db') as db:
        slot, request = db.execute('SELECT slot,request_sha256 FROM calls').fetchone()
        db.execute("UPDATE calls SET error_type='DispatchOrResponseFailure'")
    with pytest.raises(ValueError, match='reconciled saved success'):
        client.authorize_timeout_correction('researcher', 'batch-001/research', 'corrected', request, 'd' * 64)
    assert client.dispatcher.calls == 1


# Verify a complete saved object with one surplus delimiter is recovered locally,
# preserving original bytes, original failure proof and all paid reservations.
def test_complete_json_framing_recovery_reuses_paid_response(tmp_path):
    path = tmp_path / 'framing'
    registry = FakeRegistry()
    registry.adapters[runner.MODELS['validator'][0]].content = '{"decisions":[]}}'
    client = make(path, registry)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, voice='validator', stage='framing')
    with sqlite3.connect(path / 'boundary.db') as db:
        slot, request, source, raw_hash = db.execute('SELECT slot,request_sha256,source_sha256,raw_sha256 FROM calls').fetchone()
    original = (path / 'raw' / (slot + '.txt')).read_bytes()
    reserved = client.dispatcher.reserved_usd
    proof = boundary.recover_saved_json_framing(path, 'validator', 'framing', request, source, raw_hash)
    assert proof['new_provider_calls'] == 0 and not proof['semantic_content_changed']
    assert (path / 'raw' / (slot + '.txt')).read_bytes() == original
    assert proof['original_transport_failure'][2] == 'FAILED'
    assert invoke(client, voice='validator', stage='framing') == {'decisions': []}
    assert client.dispatcher.calls == 1 and client.dispatcher.reserved_usd == reserved
    assert registry.adapters[runner.MODELS['validator'][0]].calls == 1


# Verify local framing repair cannot invent missing data, choose duplicate keys,
# strip extra objects or accept arbitrary suffix text.
@pytest.mark.parametrize('text', ['{}', '{}{}', '{}]', '{}garbage', '{} }}',
                                  '{"x":1,"x":2}}', '{"x":NaN}}', '{"x":[', 'comment {} }'])
def test_framing_recovery_rejects_ambiguous_or_incomplete_output(text):
    with pytest.raises(ValueError):
        boundary._single_extra_brace(text)


# Verify altered raw response bytes cannot be rebound to the paid checkpoint.
def test_framing_recovery_rejects_raw_hash_drift(tmp_path):
    path = tmp_path / 'framing-drift'
    registry = FakeRegistry()
    registry.adapters[runner.MODELS['validator'][0]].content = '{"decisions":[]}}'
    client = make(path, registry)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, voice='validator', stage='framing')
    with sqlite3.connect(path / 'boundary.db') as db:
        slot, request, source, raw_hash = db.execute('SELECT slot,request_sha256,source_sha256,raw_sha256 FROM calls').fetchone()
    (path / 'raw' / (slot + '.txt')).write_text('{"changed":true}}')
    with pytest.raises(ValueError, match='raw response changed'):
        boundary.recover_saved_json_framing(path, 'validator', 'framing', request, source, raw_hash)
    assert states(path) == ['FAILED'] and client.dispatcher.calls == 1


# Verify the explicit wrapper handles the known harmless suffix without model
# regeneration; default transport remains strict outside this opt-in path.
def test_optin_framing_wrapper_uses_one_sdk_attempt(tmp_path):
    registry = FakeRegistry()
    registry.adapters[runner.MODELS['validator'][0]].content = '{"decisions":[]}}'
    client = make(tmp_path / 'wrapper', registry)
    result = boundary.call_with_lossless_framing(client, 'validator', 'wrapper', 'Return JSON.', PAYLOAD, 100)
    assert result == {'decisions': []}
    assert client.dispatcher.calls == 1
    assert registry.adapters[runner.MODELS['validator'][0]].calls == 1


# Verify no extra SDK attempt is made for missing JSON data or unrelated network
# failure. Neither can be repaired by dropping a syntactic trailing delimiter.
@pytest.mark.parametrize('kind', ['incomplete', 'provider'])
def test_optin_framing_wrapper_does_not_retry_real_failures(tmp_path, kind):
    registry = FakeRegistry()
    adapter = registry.adapters[runner.MODELS['validator'][0]]
    if kind == 'incomplete':
        adapter.content = '{"decisions":['
    else:
        adapter.error = TimeoutError('timed out')
    client = make(tmp_path / kind, registry)
    with pytest.raises((ValueError, boundary.SourceFirstStopped)):
        boundary.call_with_lossless_framing(client, 'validator', 'wrapper', 'Return JSON.', PAYLOAD, 100)
    assert client.dispatcher.calls == 1 and adapter.calls == 1


# Construct complete synthetic line-record output with one ambiguous evidence
# expression; return both raw text and the unaffected valid record for tests.
def quarantine_fixture():
    good = {'candidate_id': 'N002-S002', 'status': 'SUPPORTED', 'evidence_ids': ['good'], 'reason': 'unchanged'}
    bad = '{"candidate_id":"N035-S021","status":"SUPPORTED","evidence_ids":["a"].slice?[]:["b"],"reason":"preserve explanation"}'
    return '{"assessments":[\n' + bad + ',\n' + json.dumps(good) + '\n]}', good


# Verify quarantine never selects either ambiguous array and preserves the
# complete other record, with an explicit system-demotion audit trail.
def test_conditional_quarantine_preserves_other_decisions():
    raw, good = quarantine_fixture()
    result, holds = boundary._conditional_evidence_quarantine(raw, ['N035-S021', 'N002-S002'])
    assert result['assessments'][1] == good
    assert result['assessments'][0] == {'candidate_id': 'N035-S021', 'status': 'PENDING',
                                      'evidence_ids': [], 'reason': 'preserve explanation'}
    assert len(holds) == 1 and holds[0]['original_model_status'] == 'SUPPORTED'
    assert holds[0]['system_status'] == 'PENDING'


# Reject incomplete coverage, duplicated identifiers, unknown syntax and more
# than one corrupt row instead of inferring any missing evidence or decision.
@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'foreign', 'syntax', 'multiple', 'truncated'])
def test_conditional_quarantine_rejects_other_ambiguity(damage):
    raw, _ = quarantine_fixture()
    ids = ['N035-S021', 'N002-S002']
    if damage == 'missing':
        ids.append('N003-S003')
    elif damage == 'duplicate':
        raw = raw.replace('N002-S002', 'N035-S021')
    elif damage == 'foreign':
        raw = raw.replace('N035-S021', 'N099-S099')
    elif damage == 'syntax':
        raw = raw.replace('.slice?[]:', '.execute():')
    elif damage == 'multiple':
        raw = raw.replace('["good"]', '["good"].slice?[]:["other"]')
    else:
        raw = raw[:-2]
    with pytest.raises(ValueError):
        boundary._conditional_evidence_quarantine(raw, ids)


# Reconcile a synthetic complete provider response without any extra SDK call;
# raw bytes, paid reservations and original failure proof must remain intact.
def test_saved_evidence_quarantine_reuses_paid_response(tmp_path):
    path = tmp_path / 'quarantine'
    registry = FakeRegistry()
    raw, good = quarantine_fixture()
    registry.adapters[runner.MODELS['researcher'][0]].content = raw
    client = make(path, registry)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, stage='quarantine')
    with sqlite3.connect(path / 'boundary.db') as db:
        slot, request, source, raw_hash = db.execute('SELECT slot,request_sha256,source_sha256,raw_sha256 FROM calls').fetchone()
    before = (path / 'raw' / (slot + '.txt')).read_bytes()
    reserved = client.dispatcher.reserved_usd
    proof = boundary.recover_saved_evidence_quarantine(path, 'researcher', 'quarantine', request,
                  source, raw_hash, ['N035-S021', 'N002-S002'])
    assert proof['new_provider_calls'] == 0 and proof['original_transport_failure'][2] == 'FAILED'
    assert (path / 'raw' / (slot + '.txt')).read_bytes() == before
    result = invoke(client, stage='quarantine')
    assert result['assessments'][1] == good
    assert result['assessments'][0]['status'] == 'PENDING'
    assert client.dispatcher.calls == 1 and client.dispatcher.reserved_usd == reserved
    assert registry.adapters[runner.MODELS['researcher'][0]].calls == 1
    # Reopening verifies the proof rather than blindly trusting cached JSON.
    with sqlite3.connect(path / 'boundary.db') as db:
        proof['result_sha256'] = '0' * 64
        db.execute('UPDATE json_evidence_quarantines SET record_json=?', (json.dumps(proof),))
    with pytest.raises(ValueError, match='proof changed'):
        boundary.parse_saved_response(path, slot, before)


# Reject changed request/source/raw identities and missing provider attestation
# before mutating a failed row; no extra SDK attempt or reservation is allowed.
@pytest.mark.parametrize('damage', ['request', 'source', 'raw', 'provider_proof', 'voice'])
def test_saved_quarantine_rejects_binding_drift(tmp_path, damage):
    path = tmp_path / damage
    registry = FakeRegistry()
    registry.adapters[runner.MODELS['researcher'][0]].content = quarantine_fixture()[0]
    client = make(path, registry)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, stage='quarantine')
    with sqlite3.connect(path / 'boundary.db') as db:
        request, source, raw_hash = db.execute('SELECT request_sha256,source_sha256,raw_sha256 FROM calls').fetchone()
    if damage == 'request':
        request = '0' * 64
    elif damage == 'source':
        source = '0' * 64
    elif damage == 'raw':
        raw_hash = '0' * 64
    elif damage == 'provider_proof':
        with sqlite3.connect(path / 'dispatch.db') as db:
            db.execute("DELETE FROM council_dispatch_audit WHERE status='SUCCESS'")
    with pytest.raises(ValueError):
        boundary.recover_saved_evidence_quarantine(path,
            'validator' if damage == 'voice' else 'researcher', 'quarantine', request,
            source, raw_hash, ['N035-S021', 'N002-S002'])
    assert states(path) == ['FAILED'] and client.dispatcher.calls == 1


# Hold an original record whose evidence the provider subsequently disputes;
# do not execute or apply its suggested replacement or modify other records.
def test_trailing_evidence_amendment_is_ignored_not_applied():
    rows = [{'candidate_id': 'N007-S064', 'status': 'SUPPORTED', 'evidence_ids': ['placeholder']},
            {'candidate_id': 'N002-S002', 'status': 'SUPPORTED', 'evidence_ids': ['unchanged']}]
    raw = json.dumps({'assessments': rows}) + '\nCorrection: for N007-S064 the evidence ID I wrote is not in the menu. replacement ignored'
    result, holds = boundary._conditional_evidence_quarantine(raw, ['N007-S064', 'N002-S002'])
    assert result['assessments'][0] == {**rows[0], 'status': 'PENDING', 'evidence_ids': []}
    assert result['assessments'][1] == rows[1]
    assert len(holds) == 1 and holds[0]['candidate_id'] == 'N007-S064'
    with pytest.raises(ValueError):
        boundary._conditional_evidence_quarantine(raw + ' also N002-S002', ['N007-S064', 'N002-S002'])
    with pytest.raises(ValueError):
        boundary._conditional_evidence_quarantine(json.dumps({'assessments': rows}) + ' ignore everything', ['N007-S064', 'N002-S002'])


def states(path):
    """Read durable terminal statuses without provider or credential access."""
    with sqlite3.connect(path / "boundary.db") as db:
        return [r[0] for r in db.execute("SELECT status FROM calls")]


def attempts(registry):
    """Sum fake SDK attempts across all frozen roles."""
    return sum(a.calls for a in registry.adapters.values())


def test_success_resume_preserves_hashes_and_no_rebilling(tmp_path):
    """An intact success survives restart, unchanged reservations and zero calls."""
    path = tmp_path / "fresh"
    first = make(path)
    expected = invoke(first)
    assert expected["answer_mr"] == "प्रेम"
    spent = first.spend_guard.reserved_usd
    assert spent > 0
    second_registry = FakeRegistry()
    second = make(path, second_registry, resume=True)
    assert invoke(second) == expected
    assert attempts(second_registry) == 0
    assert second.dispatcher.calls == 1
    assert second.spend_guard.reserved_usd == spent
    with sqlite3.connect(path / "boundary.db") as db:
        request, source, raw, result = db.execute(
            "SELECT request_sha256,source_sha256,raw_sha256,result_sha256 FROM calls").fetchone()
    assert all(len(h) == 64 for h in (request, source, raw, result))
    assert raw == hashlib.sha256(next((path / "raw").glob("*.txt")).read_bytes()).hexdigest()


@pytest.mark.parametrize("voice", list(runner.MODELS))
def test_every_voice_uses_guard_and_dispatcher(tmp_path, voice, monkeypatch):
    """Each of five voices traverses both budgets and retains exact frozen identity."""
    client = make(tmp_path / voice)
    observed = []
    original = client.spend_guard.call

    def guarded(*args, **kwargs):
        """Observe guard entry while preserving the real dispatcher accounting."""
        observed.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(client.spend_guard, "call", guarded)
    invoke(client, voice)
    assert observed == [runner.MODELS[voice][0]]
    assert client.dispatcher.calls == 1
    assert client.dispatcher.audit[0]["provider"] == runner.PROVIDERS[voice]
    assert client.dispatcher.audit[0]["model_id"] == runner.MODELS[voice][1]
    assert client.dispatcher.audit[0]["actual_cost_usd"] is None


@pytest.mark.parametrize("changed", [
    {"system": "Changed"}, {"payload": {"sources": ["different"]}},
    {"max_output_tokens": 101},
])
def test_changed_request_is_rejected_not_recalled(tmp_path, changed):
    """System, source-containing payload and output limits are part of request identity."""
    client = make(tmp_path / "fresh")
    invoke(client)
    with pytest.raises(ValueError, match="Changed request"):
        invoke(client, **changed)
    assert attempts(client.registry) == 1


@pytest.mark.parametrize("change", [
    {"source_hashes": {"narada": "c" * 64}},
    {"max_usd": 2}, {"max_calls": 21}, {"claude_cap_usd": .6},
])
def test_resume_rejects_changed_frozen_run(tmp_path, change):
    """Sources and all reservation caps cannot silently change across resumes."""
    path = tmp_path / "fresh"
    make(path)
    registry = FakeRegistry()
    with pytest.raises(ValueError, match="configuration/source"):
        make(path, registry, resume=True, **change)
    assert attempts(registry) == 0


@pytest.mark.parametrize("field,value", [
    ("model_id", "substitute"), ("provider_name", "substitute"), ("max_tokens", 999),
])
def test_frozen_role_rejection_even_on_cached_success(tmp_path, field, value):
    """Changed roles/token defaults cannot bypass validation via a saved success."""
    client = make(tmp_path / "fresh")
    invoke(client)
    setattr(client.registry.get_adapter(runner.MODELS["researcher"][0]), field, value)
    with pytest.raises(ValueError, match="Frozen"):
        invoke(client)
    assert attempts(client.registry) == 1


def test_replaced_adapter_and_changed_rates_rejected(tmp_path):
    """Registry object swaps and mutable dispatcher rates fail before new calls."""
    client = make(tmp_path / "fresh")
    role = runner.MODELS["researcher"][0]
    client.registry.adapters[role] = FakeAdapter("researcher")
    with pytest.raises(ValueError, match="Frozen"):
        invoke(client)
    client.registry.adapters[role] = client.adapters["researcher"]
    client.dispatcher.rates[next(iter(runner.RATES))]["input"] = 999
    with pytest.raises(ValueError, match="rates"):
        invoke(client)
    assert attempts(client.registry) == 0


@pytest.mark.parametrize("voice", ["researcher", "validator", "narada"])
def test_credit_failure_stops_all_roles_and_restart_without_secret_logs(tmp_path, capsys, voice):
    """Credit/provider failures retain cost, stop the run and sanitize error details."""
    path = tmp_path / "fresh"
    registry = FakeRegistry()
    registry.get_adapter(runner.MODELS[voice][0]).error = RuntimeError("credit: " + SECRET)
    client = make(path, registry)
    with pytest.raises(boundary.SourceFirstStopped) as error:
        invoke(client, voice)
    assert SECRET not in str(error.value)
    assert states(path) == ["HARD_FAILED"]
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, "shandilya", "new-slot")
    restarted = make(path, resume=True)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(restarted, voice)
    assert attempts(registry) == 1
    assert attempts(restarted.registry) == 0
    assert restarted.dispatcher.reserved_usd > 0
    assert SECRET not in capsys.readouterr().out
    assert all(SECRET.encode() not in p.read_bytes() for p in path.rglob("*") if p.is_file())


@pytest.mark.parametrize("voice", ["researcher", "validator", "narada"])
def test_truncated_json_saved_and_hard_stopped_even_if_parseable(tmp_path, voice):
    """A truncated but valid JSON prefix is saved, never accepted or continued."""
    path = tmp_path / "fresh"
    client = make(path)
    adapter = client.registry.get_adapter(runner.MODELS[voice][0])
    adapter.truncated = True
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, voice)
    assert next((path / "raw").glob("*.txt")).read_text(encoding="utf-8") == adapter.content
    assert states(path) == ["HARD_FAILED"]
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(make(path, resume=True), voice)
    assert adapter.calls == 1


@pytest.mark.parametrize("text", [
    '{"unfinished":', '{"a":1}{"b":2}', '{"a":1,"a":2}', '{"n":NaN}',
    '[]', 'prose {"a":1}', '{"n":1e999}',
])
def test_invalid_json_is_durable_failed_and_never_repaired(tmp_path, text):
    """Malformed/ambiguous/non-object/nonfinite output is saved and stops all calls."""
    path = tmp_path / "fresh"
    client = make(path)
    client.adapters["validator"].content = text
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, "validator")
    assert states(path) == ["FAILED"]
    assert next((path / "raw").glob("*.txt")).read_text(encoding="utf-8") == text
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(make(path, resume=True), "validator")
    assert attempts(client.registry) == 1


def test_fenced_json_and_distinct_batch_slots(tmp_path):
    """Complete fenced objects work; distinct stable stages permit independent batches."""
    client = make(tmp_path / "fresh")
    client.adapters["researcher"].content = '```json\n{"ok":true}\n```'
    assert invoke(client) == {"ok": True}
    assert invoke(client, stage="batch-002/research", payload={"new": 2}) == {"ok": True}
    assert attempts(client.registry) == 2


@pytest.mark.parametrize("field,value", [
    ("response_model", "other"), ("response_provider", "other"), ("total_tokens", 0),
])
def test_invalid_response_identity_or_usage_never_succeeds(tmp_path, field, value):
    """Identity/usage failures preserve billed attempts and never become cache successes."""
    path = tmp_path / "fresh"
    client = make(path)
    setattr(client.adapters["validator"], field, value)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, "validator")
    assert states(path) == ["HARD_FAILED"]
    assert client.dispatcher.calls == 1


@pytest.mark.parametrize("kind", ["raw", "result"])
def test_corrupt_success_blocks_without_rebilling(tmp_path, kind):
    """Raw/parsed checkpoint tampering cannot be reused as valid evidence."""
    path = tmp_path / "fresh"
    client = make(path)
    invoke(client)
    if kind == "raw":
        next((path / "raw").glob("*.txt")).write_text('{"changed":true}', encoding="utf-8")
    else:
        with sqlite3.connect(path / "boundary.db") as db:
            db.execute("UPDATE calls SET result_json='{}'")
    with pytest.raises(boundary.SourceFirstStopped, match="integrity"):
        invoke(make(path, resume=True))
    assert states(path) == ["HARD_FAILED"]
    assert attempts(client.registry) == 1


def test_interrupted_attempt_is_hard_failed_on_restart(tmp_path):
    """Crash-window STARTED calls are not automatically billed again."""
    path = tmp_path / "fresh"
    client = make(path)
    invoke(client)
    with sqlite3.connect(path / "boundary.db") as db:
        db.execute("UPDATE calls SET status='STARTED',result_json=NULL")
    restarted = make(path, resume=True)
    assert states(path) == ["HARD_FAILED"]
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(restarted)
    assert attempts(restarted.registry) == 0


@pytest.mark.parametrize("cap", [{"max_usd": .000001}, {"claude_cap_usd": .000001}])
def test_budget_stop_is_durable_before_provider_attempt(tmp_path, cap):
    """Both ordinary and Claude caps stop before SDK dispatch, without retries."""
    path = tmp_path / "fresh"
    client = make(path, **cap)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    assert attempts(client.registry) == 0
    assert states(path) == ["HARD_FAILED"]


def test_call_cap_and_cached_success_after_stop(tmp_path):
    """The final successful slot stays reusable even when a later call exhausts budget."""
    client = make(tmp_path / "fresh", max_calls=1)
    expected = invoke(client)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, stage="next")
    assert invoke(client) == expected
    assert attempts(client.registry) == 1


def test_exclusive_lock_prevents_simultaneous_duplicate_call(tmp_path):
    """Concurrent entry fails closed, while the sole in-flight call finishes once."""
    client = make(tmp_path / "fresh")
    adapter = client.adapters["researcher"]
    adapter.entered, adapter.release = threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(invoke, client)
        assert adapter.entered.wait(5)
        try:
            with pytest.raises(boundary.SourceFirstStopped, match="already in use"):
                invoke(client)
        finally:
            adapter.release.set()
        assert first.result()["answer_mr"] == "प्रेम"
    assert adapter.calls == 1


def test_fresh_only_paths_and_legacy_tree_rejection(tmp_path):
    """Never adopt existing directories or create files under the old book tree."""
    with pytest.raises(FileExistsError):
        make(tmp_path)
    with pytest.raises(ValueError, match="Resume"):
        make(tmp_path / "missing", resume=True)
    for path in [runner.WORK, runner.WORK / "fresh-child"]:
        with pytest.raises(ValueError, match="Legacy"):
            make(path)


@pytest.mark.parametrize("flag", [False, None, 1, "true"])
def test_live_flag_required_before_loader_or_registry(tmp_path, flag):
    """Disabled or merely truthy flags cannot reach credential tripwires."""
    with pytest.raises(ValueError, match="enable_live"):
        boundary.create_live_provider(
            tmp_path / "live", credentials_dir=tmp_path / "never-read",
            source_hashes=SOURCES, max_usd=1, max_calls=5,
            claude_cap_usd=.5, enable_live=flag)


def test_explicit_live_factory_with_mocked_loader_never_calls_provider(tmp_path, monkeypatch):
    """Factory wiring is tested with fakes; this is not a live API connectivity test."""
    seen = []
    registry = FakeRegistry()
    for adapter in registry.adapters.values():
        adapter.offline_mode = False

    def loader(path):
        """Record synthetic loader invocation without reading any file."""
        seen.append(path)

    def registry_factory(*, offline_mode):
        """Return fakes while verifying explicit live registry construction."""
        assert offline_mode is False
        return registry

    monkeypatch.setattr(runner, "load_project_credentials", loader)
    monkeypatch.setattr("src.providers.registry.ProviderRegistry", registry_factory)
    client = boundary.create_live_provider(
        tmp_path / "fresh", credentials_dir=tmp_path / "fake",
        source_hashes=SOURCES, max_usd=1, max_calls=5, claude_cap_usd=.5, enable_live=True)
    assert seen == [tmp_path / "fake"]
    assert attempts(client.registry) == 0


def test_constructor_rejects_live_injection_without_flag(tmp_path):
    """Injecting a live adapter is not an implicit authorization to call it."""
    registry = FakeRegistry()
    registry.get_adapter(runner.MODELS["researcher"][0]).offline_mode = False
    with pytest.raises(ValueError, match="mode"):
        make(tmp_path / "fresh", registry)


def test_offline_metadata_makes_no_quality_or_billing_claim():
    """Static offline metadata clearly separates mechanics from scholarly approval."""
    metadata = boundary.offline_quality_metadata()
    assert metadata["semantic_quality_verified"] is False
    assert metadata["author_approval"] == "PENDING"
    assert "fake providers" in metadata["test_mode"]
    assert "PASS" not in json.dumps(metadata)


def test_source_binding_cannot_mutate_between_new_slots(tmp_path):
    """Source changes cannot sneak into a fresh stage within an existing run."""
    client = make(tmp_path / "fresh")
    client.source_hashes["narada"] = "c" * 64
    with pytest.raises(ValueError, match="Frozen source"):
        invoke(client)
    assert attempts(client.registry) == 0


def test_same_process_interruption_is_persisted_without_another_attempt(tmp_path):
    """A process interrupt leaves STARTED, then durably stops even without restart."""
    path = tmp_path / "fresh"
    client = make(path)
    client.adapters["researcher"].error = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        invoke(client)
    assert states(path) == ["STARTED"]
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    assert states(path) == ["HARD_FAILED"]
    assert attempts(client.registry) == 1


def test_partial_truncation_stops_other_roles_and_preserves_exact_bytes(tmp_path):
    """An unfinished JSON fragment survives locally with no continuation or fallback."""
    path = tmp_path / "fresh"
    client = make(path)
    adapter = client.adapters["researcher"]
    adapter.truncated, adapter.content = True, '{"अपूर्ण":'
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    assert next((path / "raw").glob("*.txt")).read_bytes() == adapter.content.encode("utf-8")
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client, "validator", "another")
    assert attempts(client.registry) == 1


def test_raw_persistence_failure_stops_without_rebilling(tmp_path, monkeypatch):
    """A paid response cannot be accepted when its local raw evidence fails to save."""
    path = tmp_path / "fresh"
    client = make(path)

    def fail_save(*args):
        """Simulate local storage exhaustion, without modifying unrelated files."""
        raise OSError("disk full")

    monkeypatch.setattr(client, "_raw", fail_save)
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(client)
    assert states(path) == ["HARD_FAILED"]
    with pytest.raises(boundary.SourceFirstStopped):
        invoke(make(path, resume=True))
    assert attempts(client.registry) == 1


def test_live_loader_failure_is_sanitized(tmp_path, monkeypatch):
    """Even explicit live setup must not expose credential-bearing exception text."""
    def failing_loader(path):
        """Raise a synthetic credential-bearing error without reading real secrets."""
        raise RuntimeError(SECRET)

    monkeypatch.setattr(runner, "load_project_credentials", failing_loader)
    with pytest.raises(boundary.SourceFirstStopped) as error:
        boundary.create_live_provider(
            tmp_path / "fresh", credentials_dir=tmp_path / "fake",
            source_hashes=SOURCES, max_usd=1, max_calls=5,
            claude_cap_usd=.5, enable_live=True)
    assert SECRET not in str(error.value)
