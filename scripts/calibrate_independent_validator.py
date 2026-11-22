"""Run only the existing GPT-4o fifth agent on a frozen balanced calibration set."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from scripts.run_book_council_v19 import parse_object
from scripts.run_research_book import WORK, RATES, save
from src.orchestration.independent_review import IndependentReviewer, MODEL, canonical_hash, contract_hash, verify_fixture_provenance, implementation_hash
from src.providers.openai_adapter import OpenAIAdapter
from src.providers.dispatch import BudgetedDispatcher

CORE_PATH = Path(__file__).resolve().parents[1] / "src/orchestration/independent_review.py"
ANALOGY_ROUND_IDS = ("validator-calibration-v23", "validator-calibration-v24")
EVIDENCE_ROUND_ID = "validator-calibration-v25"
DECISION_ROUND_ID = "validator-calibration-v26"


def check_calibration_reservation(db, run_id, projected):
    """Check one next reservation against the fixed authorized calibration round.

    Parameters: ledger connection, exact run ID, projected dollars. Return None;
    exceeding the ceiling or changed historical accounting raises before dispatch.
    The decision-check round is limited to v26 and $1, requiring exactly 31 prior
    calls totaling $1.7053775. The older v25 and v23/v24 guards remain unchanged;
    no historical charge is erased or allowance given to other IDs.
    The caller holds the cross-process calibration lock throughout the check/call.
    """
    total = db.execute("SELECT COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit WHERE run_id LIKE 'validator-calibration-%'").fetchone()[0]
    if run_id == DECISION_ROUND_ID:
        prior_count, prior_reserved = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit "
            "WHERE run_id LIKE 'validator-calibration-%' AND run_id != ?",
            (DECISION_ROUND_ID,)).fetchone()
        if prior_count != 31 or abs(prior_reserved - 1.7053775) > 1e-9:
            raise RuntimeError("Prior calibration ledger differs from the recorded 31-call decision-round baseline")
        if total + projected > 2.7053775 + 1e-9:
            raise RuntimeError("Decision-check calibration v26 exceeds its fixed $1 reservation")
    elif run_id == EVIDENCE_ROUND_ID:
        prior_count, prior_reserved = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit "
            "WHERE run_id LIKE 'validator-calibration-%' AND run_id != ?",
            (EVIDENCE_ROUND_ID,)).fetchone()
        if prior_count != 21 or abs(prior_reserved - 1.04303) > 1e-9:
            raise RuntimeError("Prior calibration ledger differs from the recorded 21-call evidence-round baseline")
        if total + projected > 2.04303 + 1e-9:
            raise RuntimeError("Evidence-ID calibration v25 exceeds its fixed $1 reservation")
    elif run_id in ANALOGY_ROUND_IDS:
        prior_count, prior_reserved = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(reservation_usd),0) FROM council_dispatch_audit "
            "WHERE run_id LIKE 'validator-calibration-%' AND run_id NOT IN (?,?)",
            ANALOGY_ROUND_IDS).fetchone()
        if prior_count != 9 or abs(prior_reserved - .4126475) > 1e-9:
            raise RuntimeError("Prior calibration ledger differs from the recorded nine-call baseline")
        if total + projected > 1.4126475 + 1e-9:
            raise RuntimeError("New analogy calibration round exceeds its combined $1 reservation")
    elif total + projected > 1.0:
        raise RuntimeError("Cumulative $1 validator calibration reservation exhausted")


class ValidatorRegistry:
    """Expose only the independent validator; other provider roles cannot dispatch."""

    def __init__(self, adapter):
        """Bind the unchanged GPT-4o adapter; reject substitutions before any call."""
        if adapter.provider_name != "openai" or adapter.model_id != MODEL:
            raise ValueError("Calibration requires the existing OpenAI GPT-4o validator")
        self.adapter = adapter

    def get_adapter(self, role):
        """Return the sole allowed adapter; all other roles fail before network I/O."""
        if role != "independent_validator":
            raise ValueError("Only independent_validator may run during calibration")
        return self.adapter


def compare_result(review, expected):
    """Compare semantic calibration outcome/categories; return evaluator-only evidence.

    Labels never enter prompts. A false-positive, missed defect or uncertainty
    fails the gate; this does not confer author/scholar approval on fixture text.
    """
    typed = review["typed_review"]
    categories = {issue["category"] for issue in typed["blocking_issues"]}
    rules = {issue["evidence"].get("rule") for issue in typed["blocking_issues"]
             if issue["category"] == "MECHANICAL"}
    passed = (typed["outcome"] == expected["outcome"] and
              set(expected["required_categories"]) == categories and
              not typed["uncertainties"] and
              set(expected.get("required_rules", [])) == rules)
    return {"pass": passed, "expected": expected, "observed": typed,
            "review_key": review["review_key"], "draft_sha256": review["reviewed_draft_sha256"],
            "response_normalizations": review.get("response_normalizations", []),
            "alias_recovery": review.get("alias_recovery"),
            "reference_recovery": review.get("reference_recovery"),
            "evidence_selections": review.get("evidence_selections", []),
            "decision_comparisons": review.get("decision_comparisons", [])}


def run(fixture_path, run_id="validator-calibration-v2", cap=1.0):
    """Serialize calibration runs and require IDs included in cumulative accounting.

    Return the internal run report. A concurrent process or an invalid ID fails
    before credentials; the separate SQLite lock releases even after exceptions.
    """
    if not isinstance(run_id, str) or not run_id.startswith("validator-calibration-") or not all(
            char.isalnum() or char in "-_" for char in run_id):
        raise ValueError("Calibration run ID must start with validator-calibration-")
    WORK.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(WORK / "calibration_execution_lock.db", timeout=0) as lock:
        lock.execute("BEGIN IMMEDIATE")
        return _run(fixture_path, run_id, cap)


def _run(fixture_path, run_id, cap):
    """Execute up to ten frozen probes, at most once each, under a $1 reservation.

    Inputs are local fixture path and durable run ID/cap. Return and persist an
    honest gate result. Only the OpenAI key is read, never Claude/Gemini keys.
    API/schema failures stop immediately; semantic misses finish the fixed set
    for diagnosis but cannot enable generation. No automatic retries or relabels.
    """
    if not 0 < cap <= 1.0:
        raise ValueError("Small calibration reservation ceiling must be at most $1")
    document = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    verify_fixture_provenance(document, WORK)
    fixtures = document["fixtures"]
    if len(fixtures) != 10:
        raise ValueError("Calibration requires ten frozen balanced fixtures")
    if {f["expected"]["outcome"] for f in fixtures} != {"READY", "REVISION_REQUIRED"}:
        raise ValueError("Both positive and negative controls are mandatory")
    credential = Path("C:/Users/LENOVO/Dropbox/Hiranyam AI Labs/SK_Udyog_Sutras/openai_key.txt")
    key = credential.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError("OpenAI credential reference is empty")
    adapter = OpenAIAdapter(model_id=MODEL, api_key=key, offline_mode=False,
                            max_tokens=3000, timeout_seconds=120.)
    dispatcher = BudgetedDispatcher(ValidatorRegistry(adapter), RATES, cap, len(fixtures),
                                   WORK / "dispatch.db", run_id, 3600,
                                   {"independent_validator": 120.})
    dispatcher.preflight_roles(["independent_validator"])

    def call(system, prompt):
        """Dispatch only frozen fifth agent; preserve raw responses before JSON parsing."""
        rates = RATES["openai:gpt-4o"]
        next_reservation = (adapter.estimate_tokens(system + prompt) * rates["input"] + 3000 * rates["output"]) / 1e6
        with sqlite3.connect(WORK / "dispatch.db") as db:
            check_calibration_reservation(db, run_id, next_reservation)
        response = dispatcher.call("independent_validator", prompt, system, max_output_tokens=3000,
                                   allow_truncated=True)
        if response.provider != "openai" or response.model_id != MODEL:
            raise RuntimeError("Calibration model binding changed")
        raw = WORK / "calibration_responses"
        raw.mkdir(exist_ok=True)
        (raw / f"{canonical_hash(response.content)}.txt").write_text(response.content, encoding="utf-8")
        if response.was_truncated:
            raise RuntimeError("Calibration response truncated; no automatic retry")
        return parse_object(response.content)

    reviewer = IndependentReviewer(WORK / "independent_review_v2.db", call)
    report = {"status": "RUNNING", "run_id": run_id, "model": MODEL, "claude_calls": 0,
              "calibration_round_ids": ([DECISION_ROUND_ID] if run_id == DECISION_ROUND_ID else
                                        [EVIDENCE_ROUND_ID] if run_id == EVIDENCE_ROUND_ID else
                                        list(ANALOGY_ROUND_IDS) if run_id in ANALOGY_ROUND_IDS else None),
              "calibration_round_cap_usd": 1.0,
              "fixture_sha256": canonical_hash(document), "contract_sha256": contract_hash(),
              "results": [], "author_approval": "PENDING", "scope": "Technical calibration, not scholarly certification"}
    report["implementation_sha256"] = implementation_hash()
    report["revision_candidates_sha256"] = hashlib.sha256((WORK / "revision_candidates_v2.json").read_bytes()).hexdigest()
    report_path = WORK / f"{run_id}-report.json"
    try:
        for fixture in fixtures:
            print("CALIBRATION", fixture["id"], flush=True)
            review = reviewer.review(fixture["draft"], fixture["sources"], fixture["comparators"])
            result = {"id": fixture["id"], **compare_result(review, fixture["expected"])}
            report["results"].append(result)
            save(report_path, report)
            print("PASS" if result["pass"] else "MISMATCH", flush=True)
        report["status"] = "PASS" if all(r["pass"] for r in report["results"]) else "FAIL"
    except Exception as exc:
        report.update(status="FAIL", error_type=type(exc).__name__, error=str(exc)[:400])
    finally:
        report.update(calls=dispatcher.calls, reservation_usd=dispatcher.reserved_usd,
                      actual_invoice_usd=None)
        with sqlite3.connect(WORK / "dispatch.db") as db:
            report["claude_audit_calls"] = sum(1 for (raw,) in db.execute(
                "SELECT record_json FROM council_dispatch_audit WHERE run_id=?", (run_id,))
                if json.loads(raw).get("provider") == "anthropic")
        if report["claude_audit_calls"]:
            report["status"] = "FAIL"
        save(report_path, report)
        if report["status"] == "PASS":
            save(WORK / "validator-calibration-approved.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=WORK / "validator_calibration_v2.json")
    parser.add_argument("--run-id", default="validator-calibration-v2")
    args = parser.parse_args()
    result = run(args.fixtures, args.run_id)
    print(json.dumps({k: result[k] for k in ("status", "calls", "reservation_usd", "claude_audit_calls")}, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
