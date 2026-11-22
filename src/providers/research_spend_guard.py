"""Durable, cross-run Claude reservation cap for a SINGLE calling process.

All Claude calls for one dispatch database must pass through this module in the
same process. Instances share a path-keyed lock, including across guard/run IDs.
This is NOT a cross-process budget lock: other processes or unguarded callers
must be externally serialized. No SQLite write transaction spans a provider
call, so the dispatcher's own reservation transaction cannot deadlock here.

The dispatch audit is authoritative: STARTED/FAILED/INCOMPLETE reservations are
never refunded. A guard ID freezes its cap durably. This module makes no SDK
calls, reads no credentials, changes no models, and never retries a dispatch.
Non-schema Claude dispatch failures latch a process-local stop for this database,
blocking queued Claude roles even through another guard instance. Restart only
after explicitly reconciling the failure; durable council hard failures remain.
An opted-in truncated Claude response also latches the stop, but is returned to
the parent unchanged so its partial text and metadata can be saved first.
"""

from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import threading


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_LOCK = threading.Lock()
_FAILURES: dict[str, str] = {}


class ResearchSpendLimitExceeded(RuntimeError):
    """Hard pre-call stop; callers must not automatically retry this exception."""


class ResearchProviderStopped(RuntimeError):
    """A prior Claude dispatch failed; queued roles must not make another attempt."""


def _path_key(path: object) -> str:
    """Return a canonical database-path key; invalid paths raise before dispatch."""
    return os.path.normcase(str(Path(path).resolve()))


def _amount(value: object) -> bool:
    """Recognize finite nonnegative real reservation values, excluding booleans."""
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class ResearchSpendGuard:
    """Serialize Claude calls and enforce one frozen cap across all audit run IDs.

    Instantiate as ResearchSpendGuard(dispatch_db, claude_cap_usd, guard_id).
    Use call(dispatcher, role, prompt, system, max_output_tokens=...). Other
    providers pass through without consuming the Claude allowance. No model
    substitutions, output-ceiling adjustments or provider retries are performed.
    """

    def __init__(self, audit_path: Path, claude_cap_usd: float,
                 guard_id: str = "research-claude"):
        """Freeze the cap in an existing parent directory; return a local guard.

        Inputs: dispatcher database, positive finite cap, nonblank guard ID.
        Raises ValueError on changed/invalid configuration; SQLite errors
        propagate. The guard may be created before or after the dispatcher.
        """
        if not _amount(claude_cap_usd) or claude_cap_usd <= 0:
            raise ValueError("Claude reservation cap must be positive and finite")
        if not isinstance(guard_id, str) or not guard_id.strip():
            raise ValueError("A nonempty spend guard ID is required")
        self.audit_path = Path(audit_path).resolve()
        self.claude_cap_usd = float(claude_cap_usd)
        self.guard_id = guard_id
        self._key = _path_key(self.audit_path)
        with _LOCKS_LOCK:
            self._lock = _LOCKS.setdefault(self._key, threading.RLock())
        with self._lock, closing(sqlite3.connect(self.audit_path, timeout=10)) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS research_spend_guard_config "
                           "(guard_id TEXT PRIMARY KEY, provider TEXT NOT NULL, cap_usd REAL NOT NULL)")
                db.execute("INSERT OR IGNORE INTO research_spend_guard_config VALUES (?,?,?)",
                           (guard_id, "anthropic", self.claude_cap_usd))
                self._check_config(db)

    def _check_config(self, db: sqlite3.Connection) -> None:
        """Reject changed or missing persisted cap configuration; never update it."""
        row = db.execute("SELECT provider,cap_usd FROM research_spend_guard_config WHERE guard_id=?",
                         (self.guard_id,)).fetchone()
        if row != ("anthropic", self.claude_cap_usd):
            raise ValueError("Frozen Claude spend guard configuration changed")

    def _reserved(self) -> float:
        """Sum every Anthropic reservation across runs/statuses; fail on corrupt audit.

        Called under the process lock. Return zero if dispatch has not yet
        created its audit table. Never treat missing provider metadata as free.
        """
        with closing(sqlite3.connect(self.audit_path, timeout=10)) as db:
            self._check_config(db)
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='council_dispatch_audit'").fetchone():
                return 0.0
            rows = db.execute("SELECT reservation_usd,record_json FROM council_dispatch_audit").fetchall()
        reservations = []
        for amount, raw in rows:
            try:
                record = json.loads(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("Malformed dispatch audit; Claude allowance cannot be established") from exc
            if (not isinstance(record, dict) or not isinstance(record.get("provider"), str)
                    or not record["provider"].strip() or not _amount(amount)):
                raise ValueError("Invalid dispatch reservation/provider metadata")
            if record["provider"] == "anthropic":
                reservations.append(amount)
        total = math.fsum(reservations)
        if not math.isfinite(total):
            raise ValueError("Invalid cumulative Claude reservation")
        return total

    @property
    def reserved_usd(self) -> float:
        """Read total Claude reservations across all runs, including failed calls."""
        with self._lock:
            return self._reserved()

    def _adapter(self, dispatcher, role):
        """Resolve the actual frozen adapter; reject registry/cache discrepancies."""
        adapter = dispatcher.registry.get_adapter(role)
        cached = getattr(dispatcher, "_adapters", {}).get(role)
        if cached is not None and cached is not adapter:
            raise ValueError("Dispatcher registry adapter changed; refuse cap bypass")
        frozen = getattr(dispatcher, "_role_models", {}).get(role)
        if frozen is not None and frozen != (adapter.provider_name, adapter.model_id, adapter.max_tokens):
            raise ValueError("Frozen dispatcher role/model configuration changed")
        return adapter

    def call(self, dispatcher, role: str, prompt: str, system: str = "",
             max_output_tokens: int | None = None, allow_truncated: bool = False):
        """Check shared Claude headroom, then make exactly one dispatcher call.

        Return the dispatcher's response unchanged. Use its exact rates and
        input estimator plus requested maximum output tokens for the projection.
        Budget, provider and database errors propagate without retry/refund.
        allow_truncated=True forwards partial responses unchanged for the parent
        to persist and hard-stop; a truncated Claude response also latches the
        shared stop before returning. The parent must not accept partial JSON.
        Every Claude caller must use this guard within ONE process; unrelated
        processes cannot safely share this check-and-call protocol concurrently.
        """
        if type(allow_truncated) is not bool:
            raise ValueError("allow_truncated must be a boolean")
        if getattr(dispatcher, "audit_path", None) is None or _path_key(dispatcher.audit_path) != self._key:
            raise ValueError("Spend guard requires the dispatcher's same durable audit database")
        # The provider identity is immutable. Check token ceilings only after
        # acquiring the Claude lock, since dispatch temporarily changes them.
        provider = dispatcher.registry.get_adapter(role).provider_name
        if provider != "anthropic":
            self._adapter(dispatcher, role)
            return dispatcher.call(role, prompt, system, max_output_tokens=max_output_tokens,
                                   allow_truncated=allow_truncated)
        with self._lock:
            if self._key in _FAILURES:
                raise ResearchProviderStopped(
                    f"Claude dispatch stopped after {_FAILURES[self._key]}; explicit recovery required")
            adapter = self._adapter(dispatcher, role)
            if adapter.provider_name != "anthropic":
                raise ValueError("Provider changed during Claude cap check")
            if not isinstance(prompt, str) or not isinstance(system, str):
                raise ValueError("Prompt and system must be strings")
            if max_output_tokens is not None and (
                    type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 64000):
                raise ValueError("Invalid per-call output token ceiling")
            ceiling = max_output_tokens if max_output_tokens is not None else adapter.max_tokens
            if type(ceiling) is not int or ceiling < 1:
                raise ValueError("Invalid adapter output token ceiling")
            rate = dispatcher.rates.get(f"{adapter.provider_name}:{adapter.model_id}")
            if (not isinstance(rate, dict) or not rate.get("effective_date")
                    or not _amount(rate.get("input")) or not _amount(rate.get("output"))):
                raise ValueError("Missing or invalid dated Claude reservation rates")
            tokens = adapter.estimate_tokens(system + prompt)
            if type(tokens) is not int or tokens < 0:
                raise ValueError("Invalid estimated input token count")
            projected = (tokens * rate["input"] + ceiling * rate["output"]) / 1_000_000
            if not _amount(projected):
                raise ValueError("Invalid projected Claude reservation")
            reserved = self._reserved()
            if reserved + projected > self.claude_cap_usd:
                raise ResearchSpendLimitExceeded(
                    f"Claude reservation cap exceeded before provider call: "
                    f"reserved={reserved:.9f}, projected={projected:.9f}, cap={self.claude_cap_usd:.9f}")
            try:
                response = dispatcher.call(role, prompt, system, max_output_tokens=max_output_tokens,
                                           allow_truncated=allow_truncated)
                if response.was_truncated:
                    _FAILURES[self._key] = "TruncatedProviderResponse"
                return response
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    # Store only the exception type, never credential-bearing
                    # provider messages. The shared lock closes the queued-role race.
                    _FAILURES[self._key] = type(exc).__name__
                raise
