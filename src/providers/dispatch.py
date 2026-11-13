"""One budgeted and audited dispatch boundary for all five council roles."""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from src.providers.registry import ProviderRegistry


class BudgetedDispatcher:
    """Apply a run-wide spend cap and capture only provider-exposed metadata."""

    def __init__(self, registry: ProviderRegistry, rates: Mapping[str, Dict[str, Any]],
                 max_usd: float, max_calls: int, audit_path: Path | None = None,
                 run_id: str = "default"):
        """Bind frozen role adapters and explicit per-million model rates.

        ``rates`` are keyed provider:model with input/output/effective_date and
        treated as estimates. Reject nonpositive caps. Inspect model
        key and reserve calculation to debug pre-call budget errors.
        """
        if max_usd <= 0 or max_calls < 1:
            raise ValueError("Positive run cost and call caps required")
        for key, rate in rates.items():
            if (not isinstance(rate, dict) or not rate.get("effective_date") or
                    not isinstance(rate.get("input"), (int, float)) or
                    not isinstance(rate.get("output"), (int, float)) or
                    rate["input"] < 0 or rate["output"] < 0):
                raise ValueError(f"Invalid dated model rate: {key}")
        self.registry, self.rates = registry, rates
        self.max_usd, self.max_calls = max_usd, max_calls
        self.reserved_usd = 0.0
        self.calls = 0
        self.audit: list[Dict[str, Any]] = []
        self.audit_path = Path(audit_path) if audit_path is not None else None
        self.run_id = run_id
        if self.audit_path is not None:
            with sqlite3.connect(self.audit_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS council_dispatch_audit (call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reservation_usd REAL NOT NULL, status TEXT NOT NULL, record_json TEXT NOT NULL)")
                row = db.execute("SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit WHERE run_id=?", (run_id,)).fetchone()
                self.calls, self.reserved_usd = row

    def preflight_roles(self, roles: list[str]) -> None:
        """Verify all configured role models have estimated rates before any call.

        ``roles`` is the full frozen council role list. Returns None; unknown
        roles, missing rates or insufficient minimum reservation raise. Inspect
        model keys and cap configuration to debug without exposing credentials.
        """
        minimum = 0.0
        for role in roles:
            adapter = self.registry.get_adapter(role)
            key = f"{adapter.provider_name}:{adapter.model_id}"
            if key not in self.rates:
                raise ValueError(f"Missing dated price estimate for {key}")
            input_rate, output_rate = self.rates[key]["input"], self.rates[key]["output"]
            if input_rate < 0 or output_rate < 0:
                raise ValueError("Negative model rate")
            minimum += adapter.max_tokens * output_rate / 1_000_000
        if self.max_calls < len(roles) or self.max_usd < minimum:
            raise ValueError("Budget cannot fund one five-role pass")

    def call(self, role: str, prompt: str, system_prompt: str = "") -> Any:
        """Reserve worst-case cost before invoking one configured role adapter.

        Returns ProviderResponse; unknown rates, exhausted budget, missing usage,
        truncated output or adapter errors raise and remain visible in audit.
        No HTTP status or actual bill amount is inferred. Inspect call role,
        model, timestamps and status, never credentials or raw prompts.
        """
        adapter = self.registry.get_adapter(role)
        key = f"{adapter.provider_name}:{adapter.model_id}"
        if key not in self.rates:
            raise ValueError(f"Missing dated price estimate for {key}")
        input_rate, output_rate = self.rates[key]["input"], self.rates[key]["output"]
        projected = (adapter.estimate_tokens(system_prompt + prompt) * input_rate +
                     adapter.max_tokens * output_rate) / 1_000_000
        if self.calls >= self.max_calls or self.reserved_usd + projected > self.max_usd:
            raise ValueError("Run budget or call limit exceeded before provider call")
        call_id = str(uuid.uuid4())
        record = {"role": role, "provider": adapter.provider_name, "model_id": adapter.model_id,
                  "rate_effective_date": self.rates[key]["effective_date"],
                  "timestamp": datetime.now(timezone.utc).isoformat(), "estimated_reservation_usd": projected,
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
        try:
            response = adapter.generate(prompt=prompt, system_prompt=system_prompt)
            usage = response.usage
            if not response.content or response.was_truncated or usage is None or usage.total_tokens <= 0:
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
