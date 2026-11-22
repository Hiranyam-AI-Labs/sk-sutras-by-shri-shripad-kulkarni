"""Durable source-first JSON transport; no scholarly approval or automatic retries.

Only create_live_provider loads credentials, after enable_live=True. Inject fake
offline adapters for tests. Use a NEW caller-owned directory, or explicitly resume
this boundary's own directory. Never point it at the previous research book.
All output stays local; exception messages, keys and prompts are not logged.
"""

from contextlib import contextmanager
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from scripts.run_research_book import MODELS, PROVIDERS, RATES, WORK as LEGACY_WORK
from src.providers.dispatch import BudgetedDispatcher
from src.providers.research_spend_guard import ResearchSpendGuard


class SourceFirstStopped(RuntimeError):
    """Sanitized durable failure: inspect local status/raw files, never auto-retry."""


# Classify a provider failure into a fixed public code without persisting its
# message, request headers or credentials. Returns a diagnostic enum only.
def failure_code(error):
    root = getattr(error, 'raw_error', None) or error
    message = str(root).casefold()
    status = getattr(root, 'status_code', None)
    if 'credit balance' in message and ('low' in message or 'insufficient' in message):
        return 'CREDIT_BALANCE_LOW'
    if status == 401:
        return 'AUTHENTICATION'
    if status == 429:
        return 'RATE_LIMIT'
    if isinstance(root, TimeoutError) or 'timeout' in type(root).__name__.casefold() or 'timed out' in message:
        return 'TIMEOUT'
    if 'streaming is required' in message:
        return 'SDK_STREAMING_REQUIRED'
    if status in (400, 413, 422):
        return 'PROVIDER_REQUEST_REJECTED'
    return 'UNCLASSIFIED_PROVIDER_FAILURE'


def offline_quality_metadata() -> dict:
    """Describe offline verification limits, not a claimed test run or quality pass.

    Returns static test metadata; no filesystem, credentials or provider access.
    Fake-provider tests cover transport/accounting only. Source fidelity, Marathi
    quality and production council/validator decisions require their own review.
    """
    return {
        "scope": "durable JSON transport and budget accounting only",
        "semantic_quality_verified": False,
        "author_approval": "PENDING",
        "tests": "tests/test_source_first_provider.py",
        "test_command": "python -m pytest tests/test_source_first_provider.py",
        "test_mode": "fake providers only; no paid API calls",
    }


def _json(value: Any) -> str:
    """Canonicalize strict finite JSON; invalid payloads fail before dispatch."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    """Hash canonical JSON for request/config/result bindings, never credentials."""
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _parse(text: str) -> dict:
    """Require exactly one JSON object, optionally enclosed in a JSON code fence.

    Reject duplicate keys, nonfinite values, prose and trailing objects. Invalid
    JSON is a durable FAILED call, not permission for a repair/provider retry.
    """
    def pairs(items):
        """Reject duplicate fields instead of silently overwriting evidence."""
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        """Reject JSON extensions such as NaN and Infinity."""
        raise ValueError("Nonfinite JSON constant")

    text = text.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if not match:
            raise ValueError("Invalid JSON fence")
        text = match.group(1)
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    _json(result)
    return result


# Decode only a complete strict JSON object followed by exactly one surplus
# closing brace. Return the unchanged object and framing proof. Missing data,
# duplicate keys, comments, multiple objects and other suffixes raise ValueError.
def _single_extra_brace(text):
    stripped = text.strip()
    if not stripped.startswith('{'):
        raise ValueError('Framing recovery requires an object at the beginning')
    _, end = json.JSONDecoder().raw_decode(stripped)
    if stripped[end:].strip() != '}':
        raise ValueError('Not exactly one surplus closing brace')
    prefix = stripped[:end]
    return _parse(prefix), end, hashlib.sha256(prefix.encode('utf-8')).hexdigest()


# Parse one complete strict object followed by a disputed evidence amendment.
# The caller must explicitly reconcile exact reviewed raw/request/source hashes.
# Return original records with only the disputed candidate held; never apply
# the amendment, guess replacement IDs or evaluate trailing instructions.
def _trailing_evidence_quarantine(text, expected_ids):
    stripped = text.strip()
    _, end = json.JSONDecoder().raw_decode(stripped)
    suffix = stripped[end:].strip()
    match = re.match(r'^Correction: for (N[0-9]{3}-S[0-9]{3}) the evidence ID I wrote is not in the menu\.', suffix)
    if not match or set(re.findall(r'N[0-9]{3}-S[0-9]{3}', suffix)) != {match[1]}:
        raise ValueError('Not an isolated candidate evidence amendment')
    result = _parse(stripped[:end])
    if (set(result) != {'assessments'} or not isinstance(result['assessments'], list)
            or any(not isinstance(row, dict) for row in result['assessments'])):
        raise ValueError('Complete assessment object required')
    ids = [r.get('candidate_id') for r in result['assessments']]
    if (len(ids) != len(expected_ids) or len(set(ids)) != len(ids)
            or set(ids) != set(expected_ids) or match[1] not in ids):
        raise ValueError('Exact candidate coverage required')
    row = next(r for r in result['assessments'] if r['candidate_id'] == match[1])
    if row.get('status') != 'SUPPORTED' or not isinstance(row.get('evidence_ids'), list):
        raise ValueError('Only disputed supported evidence may be held')
    before = deepcopy(row)
    row['status'], row['evidence_ids'] = 'PENDING', []
    return result, [{'candidate_id': match[1], 'original_record_sha256': _hash(before),
        'ignored_amendment_sha256': hashlib.sha256(suffix.encode()).hexdigest(),
        'original_model_status': 'SUPPORTED', 'system_status': 'PENDING',
        'reason': 'Disputed evidence amendment ignored; no replacement selected; candidate cannot advance'}]


# Parse individually valid assessment lines; quarantine one specifically known
# ambiguous conditional evidence expression without evaluating it or choosing
# either reference list. Return data plus proof. Any other corruption fails.
def _conditional_evidence_quarantine(text, expected_ids):
    lines = text.strip().splitlines()
    if len(lines) != len(expected_ids) + 2 or lines[0].strip() != '{"assessments":[' or lines[-1].strip() != ']}':
        return _trailing_evidence_quarantine(text, expected_ids)
    quoted = r'"(?:[^"\\]|\\.)*"'
    array = r'\[\s*(?:' + quoted + r'\s*(?:,\s*' + quoted + r'\s*)*)?\]'
    pattern = re.compile(r'^\{\s*"candidate_id"\s*:\s*(?P<id>' + quoted + r')\s*,\s*'
        r'"status"\s*:\s*"SUPPORTED"\s*,\s*"evidence_ids"\s*:\s*'
        r'(?P<choice>' + array + r'\.slice\?\[\]:' + array + r')(?=\s*,)')
    rows, holds = [], []
    for number, original in enumerate(lines[1:-1], 1):
        line = original.strip()
        if line.endswith(','):
            line = line[:-1]
        try:
            row = _parse(line)
        except ValueError:
            match = pattern.match(line)
            if not match:
                raise ValueError('Unknown assessment corruption; no reference may be guessed') from None
            identifier = json.loads(match['id'])
            if identifier not in expected_ids or holds:
                raise ValueError('Quarantine is limited to one exact known candidate')
            patched = line[:match.start('choice')] + '[]' + line[match.end('choice'):]
            patched = re.sub(r'("status"\s*:\s*)"SUPPORTED"', r'\1"PENDING"', patched, count=1)
            row = _parse(patched)
            if row.get('candidate_id') != identifier or row.get('status') != 'PENDING' or row.get('evidence_ids') != []:
                raise ValueError('Quarantine did not produce an excluded candidate')
            holds.append({'candidate_id': identifier, 'line_number': number + 1,
                'original_line_sha256': hashlib.sha256(original.encode()).hexdigest(),
                'original_ambiguous_evidence_expression': match['choice'],
                'original_model_status': 'SUPPORTED', 'system_status': 'PENDING',
                'reason': 'Ambiguous evidence choice; no reference guessed; candidate cannot advance'})
        rows.append(row)
    ids = [row.get('candidate_id') for row in rows]
    if len(holds) != 1 or len(set(ids)) != len(ids) or set(ids) != set(expected_ids):
        raise ValueError('Incomplete or ambiguous assessment coverage')
    return {'assessments': rows}, holds


# Read saved bytes using strict parsing or a recorded recovery proof. Framing
# recovery preserves every decision; evidence quarantine explicitly demotes one
# ambiguous candidate to PENDING with no selected references. Changed bytes,
# source, request or proof raise. Neither path accesses credentials or an SDK.
def parse_saved_response(work_dir, slot, data):
    """Verify exact saved raw/framing/composite proof; return actual logical response.

    Composite data is explicitly assembled from real prefix/completion records,
    never attributed to the original truncated SDK call. Proof drift fails closed.
    """
    with sqlite3.connect(Path(work_dir) / 'boundary.db') as composite_db:
        composite_exists = composite_db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='partial_stage_completions'").fetchone()
        composite = (composite_db.execute('SELECT receipt_path,receipt_sha256 FROM partial_stage_completions WHERE slot=?', (slot,)).fetchone()
                     if composite_exists else None)
    if composite:
        from src.orchestration.source_first_partial_completion import verify_receipt
        receipt, merged = verify_receipt(*composite)
        if (receipt['plan']['failed_slot'] != slot
                or Path(receipt['plan']['provider_work']).resolve() != Path(work_dir).resolve()
                or hashlib.sha256(data).hexdigest() != receipt['plan']['original_failed_row']['raw_sha256']):
            raise ValueError('Composite cache original identity mismatch')
        return {**merged, 'partial_stage_completion': {'path': composite[0], 'sha256': composite[1]}}
    with sqlite3.connect(Path(work_dir) / 'boundary.db') as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='json_framing_recoveries'").fetchone()
        saved = (db.execute('SELECT record_json FROM json_framing_recoveries WHERE slot=?', (slot,)).fetchone()
                 if exists else None)
        if not saved:
            quarantine_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='json_evidence_quarantines'").fetchone()
            quarantined = (db.execute('SELECT record_json FROM json_evidence_quarantines WHERE slot=?', (slot,)).fetchone()
                           if quarantine_exists else None)
            if not quarantined:
                return _parse(data.decode('utf-8'))
            proof = json.loads(quarantined[0])
            row = db.execute('SELECT request_sha256,source_sha256,raw_sha256 FROM calls WHERE slot=?', (slot,)).fetchone()
            result, holds = _conditional_evidence_quarantine(data.decode('utf-8'), proof['expected_candidate_ids'])
            if (proof['policy'] != 'ambiguous-evidence-system-hold-v1'
                    or hashlib.sha256(data).hexdigest() != proof['original_raw_sha256']
                    or row != (proof['request_sha256'], proof['source_sha256'], proof['original_raw_sha256'])
                    or holds != proof['system_holds'] or _hash(result) != proof['result_sha256']):
                raise ValueError('Saved evidence quarantine proof changed')
            return result
        proof = json.loads(saved[0])
        row = db.execute('SELECT request_sha256,source_sha256,raw_sha256 FROM calls WHERE slot=?', (slot,)).fetchone()
    result, end, prefix_hash = _single_extra_brace(data.decode('utf-8'))
    if (proof['policy'] != 'single-extra-closing-brace-v1'
            or hashlib.sha256(data).hexdigest() != proof['original_raw_sha256']
            or row != (proof['request_sha256'], proof['source_sha256'], proof['original_raw_sha256'])
            or end != proof['prefix_end_chars'] or prefix_hash != proof['prefix_sha256']
            or _hash(result) != proof['result_sha256']):
        raise ValueError('Saved JSON framing proof changed')
    return result


# Reconcile an already paid, complete response with a single surplus delimiter.
# Explicit expected request/source/raw hashes bind this offline operation. Return
# a proof; ambiguity or a truncated/foreign response raises without changing any
# bytes or reservations. The original transport failure remains in the ledger.
def recover_saved_json_framing(work_dir, voice, stage, expected_request_sha256,
                               expected_source_sha256, expected_raw_sha256):
    path = _work_path(Path(work_dir))
    if voice not in MODELS or any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                                 for value in (expected_request_sha256, expected_source_sha256, expected_raw_sha256)):
        raise ValueError('Exact saved-response identities required')
    slot = _hash([voice, stage])
    with _exclusive(path), sqlite3.connect(path / 'boundary.db') as db:
        row = db.execute('SELECT request_sha256,source_sha256,status,raw_sha256,result_json,result_sha256,error_type '
                         'FROM calls WHERE slot=?', (slot,)).fetchone()
        if (not row or row[:4] != (expected_request_sha256, expected_source_sha256, 'FAILED', expected_raw_sha256)
                or row[6] != 'InvalidJSONObject' or row[4] is not None or row[5] is not None):
            raise ValueError('Not a complete saved invalid-JSON response')
        data = (path / 'raw' / (slot + '.txt')).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_raw_sha256:
            raise ValueError('Saved raw response changed')
        result, end, prefix_hash = _single_extra_brace(data.decode('utf-8'))
        with sqlite3.connect(path / 'dispatch.db') as audit:
            matches = []
            for call_id, raw in audit.execute("SELECT call_id,record_json FROM council_dispatch_audit WHERE status='SUCCESS'"):
                item = json.loads(raw)
                if (item.get('response_sha256') == expected_raw_sha256
                        and item.get('role') == MODELS[voice][0]
                        and item.get('model_id') == MODELS[voice][1]
                        and item.get('provider') == PROVIDERS[voice]
                        and not item.get('was_truncated')
                        and item.get('finish_reason') not in ('max_tokens', 'length')):
                    matches.append(call_id)
        if len(matches) != 1:
            raise ValueError('Cannot uniquely attest complete provider response')
        proof = {'policy': 'single-extra-closing-brace-v1', 'request_sha256': row[0],
            'source_sha256': row[1], 'original_raw_sha256': row[3],
            'original_transport_failure': list(row), 'prefix_end_chars': end,
            'prefix_sha256': prefix_hash, 'result_sha256': _hash(result),
            'provider_call_id': matches[0], 'new_provider_calls': 0,
            'semantic_content_changed': False, 'raw_bytes_changed': False}
        db.execute('CREATE TABLE IF NOT EXISTS json_framing_recoveries (slot TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
        db.execute('INSERT INTO json_framing_recoveries VALUES (?,?)', (slot, _json(proof)))
        db.execute("UPDATE calls SET status='SUCCESS',result_json=?,result_sha256=?,error_type='RECOVERED_JSON_FRAMING' WHERE slot=?",
                   (_json(result), _hash(result), slot))
    return proof


# Reuse valid rows from a complete paid response while holding one ambiguous
# evidence choice. Never promotes or guesses a reference. Return explicit proof
# of the system demotion; raw model bytes and reservations remain unchanged.
# Ambiguous/truncated/foreign inputs raise before any mutation or provider call.
def recover_saved_evidence_quarantine(work_dir, voice, stage, expected_request_sha256,
                                      expected_source_sha256, expected_raw_sha256, expected_ids):
    path = _work_path(Path(work_dir))
    if (voice != 'researcher' or not isinstance(expected_ids, list)
            or any(not isinstance(i, str) for i in expected_ids)
            or len(set(expected_ids)) != len(expected_ids)):
        raise ValueError('Exact researcher batch identities required')
    slot = _hash([voice, stage])
    with _exclusive(path), sqlite3.connect(path / 'boundary.db') as db:
        row = db.execute('SELECT request_sha256,source_sha256,status,raw_sha256,result_json,result_sha256,error_type '
                         'FROM calls WHERE slot=?', (slot,)).fetchone()
        if (not row or row[:4] != (expected_request_sha256, expected_source_sha256, 'FAILED', expected_raw_sha256)
                or row[6] != 'InvalidJSONObject' or row[4] is not None or row[5] is not None):
            raise ValueError('Not a saved complete researcher JSON failure')
        data = (path / 'raw' / (slot + '.txt')).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_raw_sha256:
            raise ValueError('Saved raw response changed')
        result, holds = _conditional_evidence_quarantine(data.decode('utf-8'), expected_ids)
        with sqlite3.connect(path / 'dispatch.db') as audit:
            matches = []
            for call_id, raw in audit.execute("SELECT call_id,record_json FROM council_dispatch_audit WHERE status='SUCCESS'"):
                item = json.loads(raw)
                if (item.get('response_sha256') == expected_raw_sha256
                        and item.get('role') == MODELS[voice][0] and item.get('provider') == PROVIDERS[voice]
                        and item.get('model_id') == MODELS[voice][1] and not item.get('was_truncated')
                        and item.get('finish_reason') not in ('max_tokens', 'length')):
                    matches.append(call_id)
        if len(matches) != 1:
            raise ValueError('Complete researcher response cannot be uniquely attested')
        proof = {'policy': 'ambiguous-evidence-system-hold-v1', 'request_sha256': row[0],
            'source_sha256': row[1], 'original_raw_sha256': row[3], 'original_transport_failure': list(row),
            'expected_candidate_ids': expected_ids, 'system_holds': holds,
            'result_sha256': _hash(result), 'provider_call_id': matches[0], 'new_provider_calls': 0,
            'raw_bytes_changed': False, 'semantic_change': 'One system demotion only; all valid model records unchanged'}
        db.execute('CREATE TABLE IF NOT EXISTS json_evidence_quarantines (slot TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
        db.execute('INSERT INTO json_evidence_quarantines VALUES (?,?)', (slot, _json(proof)))
        db.execute("UPDATE calls SET status='SUCCESS',result_json=?,result_sha256=?,error_type='RECOVERED_WITH_SYSTEM_HOLD' WHERE slot=?",
                   (_json(result), _hash(result), slot))
    return proof


# Opt into the independently reviewed, lossless saved-response framing rule.
# Returns the same semantic JSON with at most one SDK call for this invocation.
# Provider failures and ambiguous/incomplete data still stop; this performs no
# paid retry and records every repaired delimiter against the original bytes.
def call_with_lossless_framing(provider, voice, stage, system, payload, tokens, *, generation_options=None):
    """Call once or replay exact success; recover only one surplus closing brace.

    Optional actual generation settings are preserved on the zero-SDK framing
    replay. Other transport/truncation/ambiguous failures remain terminal.
    """
    try:
        return provider(voice, stage, system, payload, tokens, **({"generation_options": generation_options} if generation_options is not None else {}))
    except SourceFirstStopped:
        slot = _hash([voice, stage])
        with sqlite3.connect(provider.db_path) as db:
            row = db.execute('SELECT request_sha256,source_sha256,status,raw_sha256,error_type '
                             'FROM calls WHERE slot=?', (slot,)).fetchone()
        if not row or row[2] != 'FAILED' or row[4] != 'InvalidJSONObject' or not row[3]:
            raise
        if row[1] != _hash(provider.source_hashes):
            raise ValueError('Saved framing source binding drift')
        recover_saved_json_framing(provider.work_dir, voice, stage, row[0], row[1], row[3])
        return provider(voice, stage, system, payload, tokens, **({"generation_options": generation_options} if generation_options is not None else {}))


def _work_path(work_dir: Path) -> Path:
    """Resolve the caller path and reject the legacy book tree, including aliases."""
    path = Path(work_dir).resolve()
    legacy = LEGACY_WORK.resolve()
    if path == legacy or legacy in path.parents or path in legacy.parents:
        raise ValueError("Legacy book/checkpoint directory is forbidden")
    return path


@contextmanager
def _exclusive(path: Path):
    """Hold a nonblocking OS file lock through one local call/checkpoint.

    Concurrent processes/instances fail closed rather than dispatch twice. No
    SQLite transaction spans network work; the existing guard retains its own
    single-process contract. The lock is released by the OS after a crash.
    """
    with (path / "boundary.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SourceFirstStopped("Boundary is already in use") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class SourceFirstProvider:
    """Callable JSON boundary with explicit offline injection and durable resume.

    Supply registry plus source_hashes={source_name: actual_sha256}, run budget
    and Claude cap. Registry adapters must match imported MODELS/PROVIDERS exactly.
    Offline tests must expose offline_mode=True. Live injected adapters require
    enable_live=True; only the separate live factory reads credentials.

    A (voice, stage) is ONE logical slot. Give each batch/entry a stable unique
    stage, e.g. "batch-001/research" or "entry-001/position". Changed system,
    payload, output ceiling or sources cannot silently reuse that slot. New work
    uses a fresh directory; resume=True accepts only an intact matching manifest.
    No successful transport result is an assertion of semantic quality.
    """

    def __init__(self, work_dir: Path, registry: Any, *,
                 source_hashes: Mapping[str, str], max_usd: float,
                 max_calls: int, claude_cap_usd: float,
                 resume: bool = False, enable_live: bool = False,
                 max_elapsed_seconds: int = 172800):
        """Freeze inputs and initialize durable budgets without making any call.

        Raises on nonfresh paths, changed configuration or wrong/offline roles.
        Work directory contains only this boundary's database, audit and raw
        outputs. No keys or provider exception messages enter those artifacts.
        """
        if type(enable_live) is not bool or type(resume) is not bool:
            raise ValueError("Live/resume flags must be explicit booleans")
        if (not source_hashes or any(not isinstance(k, str) or not k.strip()
                or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
                for k, v in source_hashes.items())):
            raise ValueError("Nonempty named source SHA256 bindings required")
        self.work_dir = _work_path(work_dir)
        self.registry = registry
        self.source_hashes = dict(source_hashes)
        self._source_binding = _hash(self.source_hashes)
        self.enable_live = enable_live
        self.models, self.providers, self.rates = deepcopy(MODELS), dict(PROVIDERS), deepcopy(RATES)
        self.adapters = {voice: registry.get_adapter(role)
                         for voice, (role, _) in self.models.items()}
        self._check_roles()
        self.role_tokens = {v: a.max_tokens for v, a in self.adapters.items()}
        config = {
            "version": 1, "models": self.models, "providers": self.providers,
            "rates": self.rates, "source_hashes": self.source_hashes,
            "max_usd": max_usd, "max_calls": max_calls,
            "claude_cap_usd": claude_cap_usd,
            "max_elapsed_seconds": max_elapsed_seconds,
            "role_tokens": self.role_tokens, "live": enable_live,
        }
        self.config_hash = _hash(config)
        self.db_path = self.work_dir / "boundary.db"
        if resume:
            if not self.db_path.is_file() or not (self.work_dir / "dispatch.db").is_file():
                raise ValueError("Resume requires this boundary's existing checkpoint")
        else:
            self.work_dir.mkdir(parents=True, exist_ok=False)
        with _exclusive(self.work_dir):
            with sqlite3.connect(self.db_path) as db:
                if not resume:
                    db.execute("CREATE TABLE config (digest TEXT NOT NULL)")
                    db.execute("INSERT INTO config VALUES (?)", (self.config_hash,))
                    db.execute("""CREATE TABLE calls (
                        slot TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL,
                        source_sha256 TEXT NOT NULL, status TEXT NOT NULL,
                        raw_sha256 TEXT, result_json TEXT, result_sha256 TEXT,
                        error_type TEXT)""")
                stored = db.execute("SELECT digest FROM config").fetchall()
                if stored != [(self.config_hash,)]:
                    raise ValueError("Frozen boundary configuration/source hashes changed")
                # A crash after reservation may have been billed; never repeat it.
                db.execute("UPDATE calls SET status='HARD_FAILED', error_type='InterruptedCall' "
                           "WHERE status='STARTED'")
                db.execute("""CREATE TABLE IF NOT EXISTS recovery_authorizations (
                    failed_slot TEXT PRIMARY KEY, replacement_slot TEXT UNIQUE NOT NULL,
                    voice TEXT NOT NULL, failed_stage TEXT NOT NULL, replacement_stage TEXT NOT NULL,
                    failed_request_sha256 TEXT NOT NULL, diagnostic_sha256 TEXT NOT NULL,
                    reason TEXT NOT NULL, failed_state_sha256 TEXT NOT NULL)""")
            self.dispatcher = BudgetedDispatcher(
                registry, self.rates, max_usd, max_calls,
                self.work_dir / "dispatch.db", "source-first", max_elapsed_seconds)
            self.spend_guard = ResearchSpendGuard(
                self.work_dir / "dispatch.db", claude_cap_usd, "source-first")
            (self.work_dir / "raw").mkdir(exist_ok=True)

    def authorize_timeout_correction(self, voice, failed_stage, replacement_stage,
                                     failed_request_sha256, diagnostic_sha256):
        """Authorize one diagnosed correction, never an automatic retry loop.

        Bind an old no-response failure, unchanged sources and a diagnostic hash
        to one new stage. The original failure/reservation remain intact. Raises
        unless it is the only outstanding failure and no recovery was ever used.
        Credit/authentication failures and saved partial output are ineligible.
        Caller must test/correct timeout configuration before explicit invocation
        in a fresh process; the spend guard's failed-process latch stays intact.
        """
        if (voice not in self.models or not isinstance(failed_stage, str) or not failed_stage
                or not isinstance(replacement_stage, str) or not replacement_stage
                or failed_stage == replacement_stage
                or any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                       for value in (failed_request_sha256, diagnostic_sha256))):
            raise ValueError('Exact diagnosed recovery identities required')
        failed, replacement = _hash([voice, failed_stage]), _hash([voice, replacement_stage])
        with _exclusive(self.work_dir), sqlite3.connect(self.db_path) as db:
            if db.execute('SELECT 1 FROM recovery_authorizations LIMIT 1').fetchone():
                raise ValueError('Only one explicit correction permitted per boundary')
            failures = db.execute("SELECT slot,request_sha256,status,raw_sha256,error_type,source_sha256 "
                                  "FROM calls WHERE status!='SUCCESS'").fetchall()
            if (len(failures) != 1 or failures[0][0] != failed
                    or failures[0][1] != failed_request_sha256 or failures[0][2] != 'HARD_FAILED'
                    or failures[0][3] is not None
                    or failures[0][4] not in ('DispatchOrResponseFailure', 'TIMEOUT')
                    or failures[0][5] != self._source_binding
                    or db.execute('SELECT 1 FROM calls WHERE slot=?', (replacement,)).fetchone()):
                raise ValueError('Failure is not eligible for a diagnosed timeout correction')
            self._assert_no_saved_failure_output(failed)
            db.execute('INSERT INTO recovery_authorizations VALUES (?,?,?,?,?,?,?,?,?)',
                       (failed, replacement, voice, failed_stage, replacement_stage,
                        failed_request_sha256, diagnostic_sha256, 'TIMEOUT_CONFIGURATION_CORRECTION',
                        _hash(failures[0])))

    def _assert_no_saved_failure_output(self, failed_slot):
        """Require no saved raw/temp/dispatcher partial before a paid correction.

        Parameters: exact failed slot hash. Returns None; any output, malformed
        audit or unreconciled attempt raises before reservation. All bytes stay
        intact. Global partial-output rejection is conservative because legacy
        dispatch records do not bind a boundary slot to one provider call ID.
        """
        if list((self.work_dir / 'raw').glob(failed_slot + '*')):
            raise ValueError('Saved failed-slot output requires offline reconciliation')
        saved_hashes = []
        with sqlite3.connect(self.db_path) as boundary:
            for slot, raw_hash, result_json, result_hash in boundary.execute(
                    "SELECT slot,raw_sha256,result_json,result_sha256 FROM calls WHERE status='SUCCESS'"):
                raw_path = self.work_dir / 'raw' / (slot + '.txt')
                if not raw_path.is_file():
                    raise ValueError('Saved success is missing during response reconciliation')
                data = raw_path.read_bytes()
                result = parse_saved_response(self.work_dir, slot, data)
                if (hashlib.sha256(data).hexdigest() != raw_hash
                        or _hash(result) != result_hash or _json(result) != result_json):
                    raise ValueError('Saved success integrity failed during reconciliation')
                saved_hashes.append(raw_hash)
        dispatched_hashes = []
        with sqlite3.connect(self.work_dir / 'dispatch.db') as audit:
            tables = {row[0] for row in audit.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'council_dispatch_audit' not in tables:
                raise ValueError('Missing dispatch audit prevents no-response verification')
            if ('council_partial_outputs' in tables and
                    audit.execute('SELECT 1 FROM council_partial_outputs LIMIT 1').fetchone()):
                raise ValueError('Saved dispatcher partial prevents paid correction')
            for status, record in audit.execute('SELECT status,record_json FROM council_dispatch_audit'):
                data = json.loads(record)
                if status == 'SUCCESS':
                    if not data.get('response_sha256'):
                        raise ValueError('Dispatch success lacks response identity')
                    dispatched_hashes.append(data['response_sha256'])
                    continue
                if (status != 'FAILED' or data.get('response_sha256') or data.get('content_present')
                        or data.get('was_truncated') or data.get('output_tokens', 0)):
                    raise ValueError('Dispatch response state requires offline reconciliation')
        if Counter(dispatched_hashes) != Counter(saved_hashes):
            raise ValueError('Provider response lacks an exactly reconciled saved success')

    def _verify_recovery_failure(self, db, failed_slot, expected_state):
        """Recheck the immutable failed row and saved-output absence under lock.

        Returns None; altered failure/source evidence raises before a replacement
        or later new call can spend. Does not rewrite any status or reservation.
        """
        row = db.execute('SELECT slot,request_sha256,status,raw_sha256,error_type,source_sha256 '
                         'FROM calls WHERE slot=?', (failed_slot,)).fetchone()
        if not row or _hash(row) != expected_state or row[5] != self._source_binding:
            raise ValueError('Authorized original failure changed')
        self._assert_no_saved_failure_output(failed_slot)

    def resolve_stage(self, voice, stage):
        """Return the explicitly authorized replacement stage, otherwise stage.

        Reads only a prior authorization; never creates one, retries a failed
        call, alters inputs or refunds a reservation. Invalid voices raise.
        """
        if voice not in self.models:
            raise ValueError('Unknown voice')
        with sqlite3.connect(self.db_path) as db:
            row = db.execute('SELECT replacement_stage FROM recovery_authorizations '
                             'WHERE voice=? AND failed_stage=?', (voice, stage)).fetchone()
        return row[0] if row else stage

    def future_request_parameters(self, voice, stage, system, payload, default_tokens,
                                  requested_tokens, requested_options):
        """Keep existing legacy slots exact; explicit controls affect new requests only.

        A previously controlled slot is checked against the same requested actual
        parameters by __call__; changing them fails before another SDK call.
        """
        legacy = _hash({'voice': voice, 'stage': stage, 'system': system,
                       'payload': payload, 'max_output_tokens': default_tokens,
                       'config': self.config_hash, 'sources': _hash(self.source_hashes)})
        with sqlite3.connect(self.db_path) as db:
            row = db.execute('SELECT request_sha256 FROM calls WHERE slot=?', (_hash([voice, stage]),)).fetchone()
        return ((default_tokens, None) if row and row[0] == legacy
                else (requested_tokens, requested_options))

    def _check_roles(self) -> None:
        """Check exact frozen identities, object bindings and execution mode."""
        if MODELS != self.models or PROVIDERS != self.providers or RATES != self.rates:
            raise ValueError("Frozen model/provider/rate constants changed")
        for voice, (role, model) in self.models.items():
            adapter = self.registry.get_adapter(role)
            if (adapter is not self.adapters[voice] or adapter.model_id != model
                    or adapter.provider_name != self.providers[voice]):
                raise ValueError("Frozen role model/provider changed")
            if getattr(adapter, "offline_mode", None) is not (not self.enable_live):
                raise ValueError("Adapter mode does not match explicit live flag")
            if hasattr(self, "role_tokens") and adapter.max_tokens != self.role_tokens[voice]:
                raise ValueError("Frozen role token ceiling changed")

    def _fail(self, slot: str, status: str, error_type: str) -> None:
        """Commit a sanitized terminal state; database errors propagate fail-closed."""
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE calls SET status=?,error_type=? WHERE slot=?",
                       (status, error_type, slot))

    def _raw(self, slot: str, content: str) -> str:
        """Fsync and atomically save provider text locally; return its byte hash."""
        data = content.encode("utf-8")
        target = self.work_dir / "raw" / (slot + ".txt")
        temp = target.with_suffix(".tmp")
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(target)
        return hashlib.sha256(data).hexdigest()

    def __call__(self, voice: str, stage: str, system: str,
                 payload: Any, max_output_tokens: int, *, generation_options=None) -> dict:
        """Return one parsed JSON object or raise sanitized SourceFirstStopped.

        SUCCESS is reused only after full request/source/raw/result verification,
        with zero provider calls or reservations. All calls go through the spend
        guard and dispatcher. FAILED (invalid JSON) and HARD_FAILED (provider,
        identity, truncation, budget, interrupted or persistence failure) stop
        subsequent unpaid slots durably; no retry, fallback or repair is implied.
        """
        if voice not in self.models or not isinstance(stage, str) or not stage.strip():
            raise ValueError("Known voice and nonempty unique stage required")
        if not isinstance(system, str) or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 64000:
            raise ValueError("System string and bounded integer token ceiling required")
        prompt = _json(payload)
        slot = _hash([voice, stage])
        sources = _hash(self.source_hashes)
        actual_options = deepcopy(getattr(self.adapters[voice], 'generation_options', {})
                                  if generation_options is None or generation_options == {} else generation_options)
        if actual_options:
            if (voice != 'narada' or not isinstance(actual_options, dict)
                    or set(actual_options) != {'thinking_level'}
                    or not isinstance(actual_options['thinking_level'], str)
                    or actual_options['thinking_level'].upper() not in {'LOW', 'MEDIUM', 'HIGH'}):
                raise ValueError('Explicit supported Narada thinking control required')
            actual_options['thinking_level'] = actual_options['thinking_level'].upper()
        elif not isinstance(actual_options, dict):
            raise ValueError('Generation options must be a dictionary')
        request_value = {"voice": voice, "stage": stage, "system": system,
                         "payload": payload, "max_output_tokens": max_output_tokens,
                         "config": self.config_hash, "sources": sources}
        if actual_options:
            request_value['generation_options'] = actual_options
        request = _hash(request_value)
        with _exclusive(self.work_dir):
            self._check_roles()
            from src.orchestration.source_first_partial_completion import verify_authorities
            verify_authorities(self.work_dir)
            if sources != self._source_binding:
                raise ValueError("Frozen source hashes changed")
            if self.dispatcher.rates != self.rates:
                raise ValueError("Frozen dispatch rates changed")
            with sqlite3.connect(self.db_path) as db:
                if db.execute("SELECT digest FROM config").fetchall() != [(self.config_hash,)]:
                    raise ValueError("Boundary manifest changed")
                correction = db.execute('SELECT failed_slot,failed_stage,failed_request_sha256,failed_state_sha256 '
                                        'FROM recovery_authorizations WHERE replacement_slot=?', (slot,)).fetchone()
                if correction:
                    original_request = _hash({'voice': voice, 'stage': correction[1], 'system': system,
                        'payload': payload, 'max_output_tokens': max_output_tokens,
                        'config': self.config_hash, 'sources': sources})
                    if original_request != correction[2]:
                        raise ValueError('Replacement must preserve the exact original request')
                    self._verify_recovery_failure(db, correction[0], correction[3])
                row = db.execute("SELECT request_sha256,source_sha256,status,raw_sha256,"
                                 "result_json,result_sha256 FROM calls WHERE slot=?", (slot,)).fetchone()
                if row and (row[0] != request or row[1] != sources):
                    raise ValueError("Changed request/source for existing voice/stage")
                if row and row[2] == "SUCCESS":
                    try:
                        raw = (self.work_dir / "raw" / (slot + ".txt")).read_bytes()
                        result = parse_saved_response(self.work_dir, slot, raw)
                        if (hashlib.sha256(raw).hexdigest() != row[3]
                                or _hash(result) != row[5] or _json(result) != row[4]):
                            raise ValueError("Checkpoint integrity")
                    except Exception:
                        self._fail(slot, "HARD_FAILED", "CheckpointIntegrity")
                        raise SourceFirstStopped("Saved success failed integrity validation") from None
                    return result
                failures = db.execute("SELECT slot,status FROM calls WHERE status!='SUCCESS'").fetchall()
                unresolved = []
                for failed_slot, failed_state in failures:
                    authorization = db.execute('SELECT replacement_slot,failed_state_sha256 FROM recovery_authorizations '
                                               'WHERE failed_slot=?', (failed_slot,)).fetchone()
                    recovered = (db.execute("SELECT status FROM calls WHERE slot=?", (authorization[0],)).fetchone()
                                 if authorization else None)
                    if (authorization and (authorization[0] == slot or recovered == ('SUCCESS',))):
                        self._verify_recovery_failure(db, failed_slot, authorization[1])
                        continue
                    unresolved.append((failed_slot, failed_state))
                if unresolved:
                    db.execute("UPDATE calls SET status='HARD_FAILED',error_type='InterruptedCall' "
                               "WHERE status='STARTED'")
                    db.commit()
                    raise SourceFirstStopped("Durable failed/interrupted call; explicit recovery required")
                db.execute("INSERT INTO calls (slot,request_sha256,source_sha256,status) "
                           "VALUES (?,?,?,'STARTED')", (slot, request, sources))
            try:
                role, model = self.models[voice]
                adapter = self.adapters[voice]
                previous_thinking = getattr(adapter, 'thinking_level', None)
                if actual_options:
                    adapter.thinking_level = actual_options['thinking_level']
                try:
                    response = self.spend_guard.call(
                        self.dispatcher, role, prompt, system,
                        max_output_tokens=max_output_tokens, allow_truncated=True)
                finally:
                    if actual_options:
                        adapter.thinking_level = previous_thinking
                raw_hash = self._raw(slot, response.content)
                with sqlite3.connect(self.db_path) as db:
                    db.execute("UPDATE calls SET raw_sha256=? WHERE slot=?", (raw_hash, slot))
                if response.provider != self.providers[voice] or response.model_id != model:
                    raise SourceFirstStopped("Provider response identity changed")
                if response.was_truncated:
                    raise SourceFirstStopped("Truncated response saved locally; execution stopped")
            except Exception as error:
                code = failure_code(error)
                self._fail(slot, "HARD_FAILED", code)
                raise SourceFirstStopped(f"Provider call stopped ({code}); no automatic retry") from None
            try:
                result = _parse(response.content)
            except Exception:
                self._fail(slot, "FAILED", "InvalidJSONObject")
                raise SourceFirstStopped("Invalid JSON saved locally; no automatic retry") from None
            try:
                with sqlite3.connect(self.db_path) as db:
                    db.execute("UPDATE calls SET status='SUCCESS',result_json=?,result_sha256=? WHERE slot=?",
                               (_json(result), _hash(result), slot))
            except Exception:
                self._fail(slot, "HARD_FAILED", "CheckpointWriteFailure")
                raise SourceFirstStopped("Checkpoint write failed; no automatic retry") from None
            return result


def create_live_provider(work_dir: Path, *, credentials_dir: Path,
                         source_hashes: Mapping[str, str], max_usd: float,
                         max_calls: int, claude_cap_usd: float,
                         enable_live: bool = False, resume: bool = False,
                         max_elapsed_seconds: int = 172800) -> SourceFirstProvider:
    """Explicitly load existing credentials and build unchanged live adapters.

    enable_live MUST be exactly True before any credential loader/adapter is
    constructed. This factory makes no provider call. SDK retries are disabled
    by existing adapters; no continuation API is used. Never logs credential
    paths/values or original exception text. Fake-only tests patch this loader
    and registry, so offline test results do not assert live connectivity.
    """
    if enable_live is not True:
        raise ValueError("enable_live=True required before loading credentials")
    path = _work_path(work_dir)
    if not resume and path.exists():
        raise ValueError("Fresh work directory required")
    if resume and not (path / "boundary.db").is_file():
        raise ValueError("Resume requires this boundary's existing checkpoint")
    from scripts.run_research_book import load_project_credentials
    from src.providers.registry import ProviderRegistry
    try:
        load_project_credentials(Path(credentials_dir))
        registry = ProviderRegistry(offline_mode=False)
    except Exception:
        raise SourceFirstStopped("Live credential/registry setup failed") from None
    return SourceFirstProvider(
        path, registry, source_hashes=source_hashes, max_usd=max_usd,
        max_calls=max_calls, claude_cap_usd=claude_cap_usd, resume=resume,
        enable_live=True, max_elapsed_seconds=max_elapsed_seconds)
