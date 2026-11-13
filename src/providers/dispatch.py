"""One budgeted and audited dispatch boundary for all five council roles."""

import hashlib
import json
import math
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from src.providers.registry import ProviderRegistry


class BudgetedDispatcher:
    """Apply a run-wide spend cap and capture only provider-exposed metadata."""

    def __init__(self, registry: ProviderRegistry, rates: Mapping[str, Dict[str, Any]],
                 max_usd: float, max_calls: int, audit_path: Path | None = None,
                 run_id: str = "default", max_elapsed_seconds: int = 600,
                 role_timeouts: Mapping[str, float] | None = None):
        """Bind frozen role adapters and explicit per-million model rates.

        ``rates`` are keyed provider:model with input/output/effective_date and
        treated as estimates. Reject nonpositive caps. Inspect model
        key and reserve calculation to debug pre-call budget errors.
        """
        if (not isinstance(max_usd, (int, float)) or not math.isfinite(max_usd) or
                max_usd <= 0 or max_calls < 1 or max_elapsed_seconds < 1):
            raise ValueError("Positive run cost and call caps required")
        for key, rate in rates.items():
            if (not isinstance(rate, dict) or not rate.get("effective_date") or
                    not isinstance(rate.get("input"), (int, float)) or
                    not isinstance(rate.get("output"), (int, float)) or
                    not math.isfinite(rate["input"]) or not math.isfinite(rate["output"]) or
                    rate["input"] < 0 or rate["output"] < 0):
                raise ValueError(f"Invalid dated model rate: {key}")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
               for value in (role_timeouts or {}).values()):
            raise ValueError("Role timeouts must be positive finite seconds")
        self.registry = registry
        self.rates = {key: dict(value) for key, value in rates.items()}
        self._adapters: dict[str, Any] = {}
        self._role_models: dict[str, tuple[str, str, int]] = {}
        self.max_usd, self.max_calls = max_usd, max_calls
        self.max_elapsed_seconds = max_elapsed_seconds
        self.role_timeouts = dict(role_timeouts or {})
        self.deadline = time.time() + max_elapsed_seconds
        self.reserved_usd = 0.0
        self.calls = 0
        self.audit: list[Dict[str, Any]] = []
        self.audit_path = Path(audit_path) if audit_path is not None else None
        self.run_id = run_id
        if self.audit_path is not None:
            with sqlite3.connect(self.audit_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS council_dispatch_audit (call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reservation_usd REAL NOT NULL, status TEXT NOT NULL, record_json TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS council_run_config (run_id TEXT PRIMARY KEY, config_sha256 TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS council_role_config (run_id TEXT NOT NULL, role TEXT NOT NULL, provider TEXT NOT NULL, model_id TEXT NOT NULL, max_tokens INTEGER NOT NULL, PRIMARY KEY(run_id,role))")
                db.execute("CREATE TABLE IF NOT EXISTS council_run_deadline (run_id TEXT PRIMARY KEY, deadline REAL NOT NULL)")
                db.execute("INSERT OR IGNORE INTO council_run_deadline VALUES (?,?)", (run_id, self.deadline))
                self.deadline = db.execute("SELECT deadline FROM council_run_deadline WHERE run_id=?", (run_id,)).fetchone()[0]
                config = {"rates": self.rates, "max_usd": self.max_usd,
                          "max_calls": self.max_calls, "max_elapsed_seconds": max_elapsed_seconds,
                          "role_timeouts": self.role_timeouts}
                digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
                db.execute("INSERT OR IGNORE INTO council_run_config VALUES (?,?)", (run_id, digest))
                stored = db.execute("SELECT config_sha256 FROM council_run_config WHERE run_id=?", (run_id,)).fetchone()[0]
                if stored != digest:
                    raise ValueError("Durable run pricing or budget configuration changed")
                row = db.execute("SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit WHERE run_id=?", (run_id,)).fetchone()
                self.calls, self.reserved_usd = row

    def preflight_roles(self, roles: list[str]) -> None:
        """Verify all configured role models have estimated rates before any call.

        ``roles`` is the full frozen council role list. Returns None; unknown
        roles, missing rates or insufficient minimum reservation raise. Inspect
        model keys and cap configuration to debug without exposing credentials.
        """
        if time.time() >= self.deadline:
            raise ValueError("Run wall-clock deadline exhausted")
        minimum = 0.0
        for role in roles:
            adapter = self.registry.get_adapter(role)
            model = (adapter.provider_name, adapter.model_id, adapter.max_tokens)
            if role in self._role_models and self._role_models[role] != model:
                raise ValueError("Frozen role model changed during run")
            self._adapters[role], self._role_models[role] = adapter, model
            self._freeze_role(role, model)
            key = f"{adapter.provider_name}:{adapter.model_id}"
            if key not in self.rates:
                raise ValueError(f"Missing dated price estimate for {key}")
            input_rate, output_rate = self.rates[key]["input"], self.rates[key]["output"]
            if input_rate < 0 or output_rate < 0:
                raise ValueError("Negative model rate")
            minimum += adapter.max_tokens * output_rate / 1_000_000
        if self.max_calls < len(roles) or self.max_usd < minimum:
            raise ValueError("Budget cannot fund one five-role pass")

    def call(self, role: str, prompt: str, system_prompt: str = "",
             max_output_tokens: int | None = None) -> Any:
        """Reserve worst-case cost before invoking one configured role adapter.

        Returns ProviderResponse; unknown rates, exhausted budget, missing usage,
        truncated output or adapter errors raise and remain visible in audit.
        No HTTP status or actual bill amount is inferred. Inspect call role,
        model, timestamps and status, never credentials or raw prompts.
        """
        if time.time() >= self.deadline:
            raise ValueError("Run wall-clock deadline exhausted before provider call")
        adapter = self._adapters.get(role)
        if adapter is None:
            adapter = self.registry.get_adapter(role)
            self._adapters[role] = adapter
            self._role_models[role] = (adapter.provider_name, adapter.model_id, adapter.max_tokens)
        if (adapter.provider_name, adapter.model_id, adapter.max_tokens) != self._role_models[role]:
            raise ValueError("Frozen role adapter configuration changed")
        self._freeze_role(role, self._role_models[role])
        if (max_output_tokens is not None and
                (isinstance(max_output_tokens, bool) or
                 not isinstance(max_output_tokens, int) or
                 not 1 <= max_output_tokens <= 64000)):
            raise ValueError("Invalid per-call output token ceiling")
        output_ceiling = max_output_tokens or adapter.max_tokens
        key = f"{adapter.provider_name}:{adapter.model_id}"
        if key not in self.rates:
            raise ValueError(f"Missing dated price estimate for {key}")
        input_rate, output_rate = self.rates[key]["input"], self.rates[key]["output"]
        projected = (adapter.estimate_tokens(system_prompt + prompt) * input_rate +
                     output_ceiling * output_rate) / 1_000_000
        if not math.isfinite(projected) or projected < 0:
            raise ValueError("Invalid model cost reservation")
        if self.calls >= self.max_calls or self.reserved_usd + projected > self.max_usd:
            raise ValueError("Run budget or call limit exceeded before provider call")
        call_id = str(uuid.uuid4())
        record = {"role": role, "provider": adapter.provider_name, "model_id": adapter.model_id,
                  "rate_effective_date": self.rates[key]["effective_date"],
                  "timestamp": datetime.now(timezone.utc).isoformat(), "estimated_reservation_usd": projected,
                  "max_output_tokens": output_ceiling,
                  "http_status": None, "actual_cost_usd": None, "status": "STARTED"}
        if self.audit_path is not None:
            # BEGIN IMMEDIATE serializes multi-process budget reservations. Failed
            # calls keep their reservation because usage may be billed or unknown.
            with sqlite3.connect(self.audit_path, timeout=10) as db:
                db.execute("BEGIN IMMEDIATE")
                count, spent = db.execute("SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit WHERE run_id=?", (self.run_id,)).fetchone()
                if count >= self.max_calls or spent + projected > self.max_usd:
                    raise ValueError("Durable run budget exhausted before provider call")
                db.execute("INSERT INTO council_dispatch_audit VALUES (?,?,?,?,?)",
                           (call_id, self.run_id, projected, "STARTED", json.dumps(record)))
                self.calls, self.reserved_usd = count + 1, spent + projected
        else:
            self.calls += 1
            self.reserved_usd += projected
        self.audit.append(record)
        original_timeout = getattr(adapter, "timeout_seconds", None)
        original_max_tokens = adapter.max_tokens
        remaining = self.deadline - time.time()
        if remaining <= 0:
            record.update(status="FAILED", error_type="RunDeadlineExceeded")
            self._persist_result(call_id, record)
            raise ValueError("Run deadline exhausted after reservation")
        if original_timeout is not None:
            requested_timeout = self.role_timeouts.get(role, original_timeout)
            adapter.timeout_seconds = min(requested_timeout, remaining)
            record["effective_timeout_seconds"] = adapter.timeout_seconds
        adapter.max_tokens = output_ceiling
        try:
            response = adapter.generate(prompt=prompt, system_prompt=system_prompt)
            usage = response.usage
            if not response.content or response.was_truncated or usage is None or usage.total_tokens <= 0:
                record.update(finish_reason=response.finish_reason,
                              was_truncated=bool(response.was_truncated),
                              content_present=bool(response.content),
                              usage_present=usage is not None)
                if usage is not None:
                    record.update(input_tokens=usage.input_tokens,
                                  output_tokens=usage.output_tokens)
                raise ValueError("Provider response incomplete or usage unavailable")
            record.update(status="SUCCESS", finish_reason=response.finish_reason,
                          input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                          response_sha256=hashlib.sha256(response.content.encode("utf-8")).hexdigest(),
                          actual_cost_usd=usage.actual_cost_usd)
            self._persist_result(call_id, record)
            return response
        except Exception as exc:
            record.update(status="FAILED", error_type=type(exc).__name__)
            self._persist_result(call_id, record)
            raise
        finally:
            adapter.max_tokens = original_max_tokens
            if original_timeout is not None:
                adapter.timeout_seconds = original_timeout

    def _freeze_role(self, role: str, model: tuple[str, str, int]) -> None:
        """Bind a role's exact provider, model ID and token ceiling across restarts."""
        if self.audit_path is None:
            return
        with sqlite3.connect(self.audit_path) as db:
            db.execute("INSERT OR IGNORE INTO council_role_config VALUES (?,?,?,?,?)",
                       (self.run_id, role, *model))
            stored = db.execute("SELECT provider,model_id,max_tokens FROM council_role_config WHERE run_id=? AND role=?",
                                (self.run_id, role)).fetchone()
            if tuple(stored) != model:
                raise ValueError("Durable role model assignment changed")

    def _persist_result(self, call_id: str, record: Dict[str, Any]) -> None:
        """Update one reserved call with observed status and sanitized metadata.

        ``call_id`` identifies the reservation and ``record`` excludes prompts and
        secrets. Returns None; SQLite errors propagate to block false acceptance.
        Inspect run/call IDs and transaction state for recovery.
        """
        if self.audit_path is not None:
            with sqlite3.connect(self.audit_path) as db:
                changed = db.execute("UPDATE council_dispatch_audit SET status=?,record_json=? WHERE call_id=? AND run_id=?",
                                     (record["status"], json.dumps(record), call_id, self.run_id)).rowcount
                if changed != 1:
                    raise RuntimeError("Call audit persistence failed")
