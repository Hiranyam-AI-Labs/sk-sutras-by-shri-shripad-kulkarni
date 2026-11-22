"""Supervise only the diagnosed missing-decision-coverage recovery; no model changes.

Explicit CLI execution may call existing budgeted production/recovery entry points.
Importing this module does not load credentials or call providers. Run only after
the existing production process stops; the lock excludes other supervisors only.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_research_book import WORK
from src.orchestration.independent_review import canonical_hash, _coverage_request, _COVERAGE_TABLE

RUN_OPTIONS = {"target": 100, "budget": 50.891999, "run_id": "full-book-v26",
               "claude_cap": 35., "allow_exclusions": True, "review_v2": True}
INVALID_REVIEW = "Independent review invalid or unavailable; no composition rewrite authorized"
CACHED_REVIEW = "Independent review previously failed or is in flight; no automatic retry"


def eligible_review(work, report):
    """Find the latest review for the next entry and validate narrow eligibility.

    Return key plus immutable request/raw hashes. Any different report, missing or
    stale evidence, or existing recovery in any state raises before recovery.
    This function opens the review database read-only and never loads credentials.
    """
    if (report.get("status") != "STOPPED" or report.get("error_type") != "RuntimeError" or
            report.get("error") not in (INVALID_REVIEW, CACHED_REVIEW) or report.get("run_id") != RUN_OPTIONS["run_id"] or
            report.get("target") != 100):
        raise ValueError("Not the diagnosed independent-review stop")
    attempted = report.get("attempted")
    if (not isinstance(attempted, list) or any(type(n) is not int for n in attempted) or
            attempted != list(range(1, len(attempted) + 1)) or len(attempted) >= 100):
        raise ValueError("Report does not identify a unique next entry")
    number = max(attempted, default=0) + 1
    path = Path(work).resolve() / "independent_review_v2.db"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        selected = None
        for row in db.execute("SELECT review_key,state,request_json,response_json,error FROM independent_reviews_v2 ORDER BY rowid DESC"):
            request = json.loads(row[2])
            if request.get("payload", {}).get("current_draft", {}).get("number") == number:
                selected = row
                break
        if selected is None:
            raise ValueError("No current review found for next entry")
        key = selected[0]
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_COVERAGE_TABLE,)).fetchone():
            if db.execute(f"SELECT 1 FROM {_COVERAGE_TABLE} WHERE review_key=?", (key,)).fetchone():
                raise ValueError("A recovery attempt already exists; no automatic retry")
        bound = _coverage_request(key, selected[1:])
    return {"review_key": key, "number": number, "recovery_request_sha256": canonical_hash(bound),
            "original_request_sha256": bound["original_request_sha256"],
            "original_raw_sha256": bound["original_raw_sha256"]}


def run(*, work=WORK, generate=None, recover=None, max_recoveries=100):
    """Run fixed production settings and at most one recovery per diagnosed key.

    Optional callbacks are for offline tests; defaults use existing budgeted
    entry points. max_recoveries may reduce, never exceed, 100 across this audit
    history. Return terminal status with author approval pending. Every report and
    pre-call reservation is saved as a hash-checked, exclusive-create audit file.
    Unknown/provider/budget/quality/recovery errors stop; there are no retries.
    """
    if type(max_recoveries) is not int or not 1 <= max_recoveries <= 100:
        raise ValueError("Supervisor recovery bound must be between 1 and 100")
    if generate is None:
        from scripts.run_research_book import run as generate
    if recover is None:
        from scripts.recover_review_coverage import run as recover
    work = Path(work).resolve()
    audit = work / "supervisor_attempts"
    audit.mkdir(exist_ok=True)
    # Separate from dispatch/review databases: never hold their write locks over calls.
    with sqlite3.connect(audit / "execution_lock.db", timeout=0) as lock:
        lock.execute("BEGIN IMMEDIATE")
        events = []
        for path in sorted(audit.glob("event-*.json")):
            event = json.loads(path.read_text(encoding="utf-8"))
            digest = event.pop("sha256")
            if canonical_hash(event) != digest or event["sequence"] != len(events) + 1:
                raise ValueError("Supervisor audit hash or sequence changed")
            events.append(event)
        reservations = [e["data"]["review_key"] for e in events if e["event"] == "recovery_reserved"]
        if len(set(reservations)) != len(reservations):
            raise ValueError("Duplicate supervisor recovery reservation")
        seen = set(reservations)

        def record(kind, data):
            """Persist one immutable evidence record before proceeding; no secret inputs."""
            value = {"sequence": len(events) + 1, "event": kind, "data": data,
                     "utc": datetime.now(timezone.utc).isoformat(), "run_options": RUN_OPTIONS,
                     "author_approval": "PENDING"}
            path = audit / f"event-{value['sequence']:05d}.json"
            with path.open("x", encoding="utf-8") as stream:
                json.dump({**value, "sha256": canonical_hash(value)}, stream, ensure_ascii=False, indent=2)
                stream.flush()
            events.append(value)

        def stop(reason, status="STOPPED"):
            """Save and return a terminal decision without author approval or retries."""
            result = {"status": status, "reason": reason, "recoveries_reserved": len(seen),
                      "author_approval": "PENDING", "run_id": RUN_OPTIONS["run_id"]}
            record("terminal", result)
            return result

        while True:
            record("generation_started", {})
            try:
                report = generate(**RUN_OPTIONS)
            except Exception as exc:
                return stop("Generation raised " + type(exc).__name__)
            if not isinstance(report, dict):
                return stop("Generation returned an invalid report")
            record("generation_report", {"report_sha256": canonical_hash(report), "report": report})
            if report.get("status") in {"READY_FOR_AUTHOR_REVIEW", "READY_FOR_AUTHOR_REVIEW_WITH_EXCLUSIONS"}:
                return stop("Production reached its terminal review state", report["status"])
            if report.get("status") == "QUALITY_STOP":
                return stop("Production quality stop", "QUALITY_STOP")
            try:
                candidate = eligible_review(work, report)
            except Exception as exc:
                return stop("No eligible coverage recovery: " + type(exc).__name__)
            key = candidate["review_key"]
            if key in seen or len(seen) >= max_recoveries:
                return stop("Supervisor distinct-key or recovery limit reached")
            record("recovery_reserved", candidate)
            seen.add(key)
            try:
                # Recheck immediately before the existing helper loads a credential.
                if eligible_review(work, report) != candidate:
                    raise ValueError("Coverage recovery evidence changed")
                result = recover(key)
                if (not isinstance(result, dict) or result.get("review_key") != key or
                        result.get("kind") != "missing-decision-coverage-v1" or result.get("provider_calls") != 1):
                    raise ValueError("Recovery returned invalid audit metadata")
            except Exception as exc:
                record("recovery_failed", {"review_key": key, "error_type": type(exc).__name__})
                return stop("Explicit coverage recovery failed")
            record("recovery_complete", {"review_key": key, "result_sha256": canonical_hash(result), "result": result})


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"].startswith("READY_FOR_AUTHOR_REVIEW") else 1)
