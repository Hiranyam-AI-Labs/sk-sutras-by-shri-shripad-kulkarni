"""Offline supervisor policy tests; all generation and recovery callbacks are mocks."""

import json
import sqlite3
from unittest.mock import Mock

import pytest

from scripts import resume_research_book_supervised as supervisor
from src.orchestration import independent_review as review


def failed_review(work, number=28, error=None, checks=None):
    """Persist an actual hashed 27-card failure without calling a model."""
    draft = {"id": f"NEW-{number:03d}", "number": number, "title_mr": "विचार",
             "new_sutra": "उद्यमेन विवेकः", "exposition": ["विचार " * 500],
             "references": [], "examples": [], "summary_mr": "गरज तपासा", "action_mr": "प्रश्न विचारा"}
    cards = [{"id": f"NEW-{n:03d}", "formula": f"पूर्व सूत्र {n}",
              "decision_mr": f"निर्णय {n}", "action_mr": f"कृती {n}"} for n in range(1, number)]
    payload = review.build_payload(draft, {"references": [], "examples": []}, cards)
    request = {"contract_hash": review.contract_hash(), "payload": payload,
               "prompt": review.CONTRACT + "\nEVIDENCE\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True),
               "system": review.SYSTEM}
    key = review.canonical_hash(request)
    raw = {"decision_checks": {"NEW-001": "DISTINCT"} if checks is None else checks,
           "source_checks": [], "outcome": "READY", "blocking_issues": [], "advisory_notes": [], "uncertainties": []}
    with sqlite3.connect(work / "independent_review_v2.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS independent_reviews_v2(review_key TEXT PRIMARY KEY,state TEXT,request_json TEXT,response_json TEXT,error TEXT)")
        db.execute("INSERT INTO independent_reviews_v2 VALUES (?,'FAILED',?,?,?)",
                   (key, json.dumps(request), json.dumps(raw), error or review._COVERAGE_ERROR))
    return key


def report(number=28, **changes):
    """Create the exact production stop shape, with deliberate variations allowed."""
    value = {"status": "STOPPED", "error_type": "RuntimeError", "error": supervisor.INVALID_REVIEW,
             "run_id": "full-book-v26", "target": 100, "attempted": list(range(1, number))}
    return {**value, **changes}


def recovered(key):
    """Represent the successful existing bounded helper's audit metadata."""
    return {"kind": "missing-decision-coverage-v1", "review_key": key, "provider_calls": 1}


def test_exact_failure_recovers_once_then_resumes_fixed_budget(tmp_path):
    """Only eligible coverage failure reaches recovery; every run keeps exact caps."""
    key = failed_review(tmp_path)
    generate = Mock(side_effect=[report(), report(status="READY_FOR_AUTHOR_REVIEW")])
    recover = Mock(side_effect=recovered)
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["author_approval"] == "PENDING"
    recover.assert_called_once_with(key)
    assert generate.call_count == 2
    for call in generate.call_args_list:
        assert call.kwargs == {"target": 100, "budget": 50.891999, "run_id": "full-book-v26",
                               "claude_cap": 35., "allow_exclusions": True, "review_v2": True}
    events = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((tmp_path / "supervisor_attempts").glob("event-*.json"))]
    for event in events:
        digest = event.pop("sha256")
        assert review.canonical_hash(event) == digest
    saved = next(e["data"] for e in events if e["event"] == "generation_report")
    assert saved["report"] == report() and saved["report_sha256"] == review.canonical_hash(report())
    reserved = next(e["data"] for e in events if e["event"] == "recovery_reserved")
    assert reserved["review_key"] == key and reserved["number"] == 28


def test_cached_failure_report_recovers_only_valid_failed_coverage(tmp_path):
    """A restarted runner's exact cache error may identify the same eligible failure."""
    key = failed_review(tmp_path)
    generate = Mock(side_effect=[report(error=supervisor.CACHED_REVIEW),
                                 report(status="READY_FOR_AUTHOR_REVIEW")])
    recover = Mock(side_effect=recovered)
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW"
    recover.assert_called_once_with(key)
    assert generate.call_count == 2


def test_cached_report_with_actual_inflight_review_never_recovers(tmp_path):
    """The shared cache error cannot turn a real RUNNING review into an eligible failure."""
    failed_review(tmp_path)
    with sqlite3.connect(tmp_path / "independent_review_v2.db") as db:
        db.execute("UPDATE independent_reviews_v2 SET state='RUNNING',response_json=NULL,error=NULL")
    generate = Mock(return_value=report(error=supervisor.CACHED_REVIEW))
    recover = Mock()
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover)
    assert result["status"] == "STOPPED" and result["recoveries_reserved"] == 0
    generate.assert_called_once()
    recover.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"status": "QUALITY_STOP"}, {"error": "Provider response truncated"},
    {"error": "Run budget exceeded"}, {"error_type": "ValueError"},
    {"run_id": "another-run"}, {"target": 99}, {"attempted": [1, 3]},
    {"error": supervisor.INVALID_REVIEW + " extra"},
])
def test_other_reports_never_recover(tmp_path, changes):
    """Quality, provider, budget and malformed reports all stop without recovery."""
    failed_review(tmp_path)
    generate, recover = Mock(return_value=report(**changes)), Mock()
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover)
    assert result["status"] in {"STOPPED", "QUALITY_STOP"}
    generate.assert_called_once()
    recover.assert_not_called()


@pytest.mark.parametrize("state", ["RUNNING", "FAILED", "COMPLETE"])
def test_any_existing_recovery_attempt_stops(tmp_path, state):
    """An existing record never authorizes another call, including COMPLETE records."""
    key = failed_review(tmp_path)
    with sqlite3.connect(tmp_path / "independent_review_v2.db") as db:
        db.execute(f"CREATE TABLE {review._COVERAGE_TABLE}(review_key TEXT PRIMARY KEY,state TEXT)")
        db.execute(f"INSERT INTO {review._COVERAGE_TABLE} VALUES (?,?)", (key, state))
    recover = Mock()
    result = supervisor.run(work=tmp_path, generate=Mock(return_value=report()), recover=recover)
    assert result["status"] == "STOPPED"
    recover.assert_not_called()


@pytest.mark.parametrize("defect", ["other_error", "unknown_id", "wrong_entry", "changed_hash"])
def test_ineligible_cache_never_recovers(tmp_path, defect):
    """Use the real coverage eligibility function; no fabricated checks or IDs."""
    failed_review(tmp_path, number=29 if defect == "wrong_entry" else 28,
                  error="ValueError: Wrong reference" if defect == "other_error" else None,
                  checks={"UNKNOWN": "DISTINCT"} if defect == "unknown_id" else None)
    if defect == "changed_hash":
        with sqlite3.connect(tmp_path / "independent_review_v2.db") as db:
            db.execute("UPDATE independent_reviews_v2 SET review_key='changed'")
    recover = Mock()
    assert supervisor.run(work=tmp_path, generate=Mock(return_value=report()), recover=recover)["status"] == "STOPPED"
    recover.assert_not_called()


def test_recovery_failure_stops_without_generation_retry(tmp_path):
    """Provider/helper failure is terminal, retaining the pre-call audit reservation."""
    failed_review(tmp_path)
    generate, recover = Mock(return_value=report()), Mock(side_effect=RuntimeError("failed"))
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover)
    assert result["status"] == "STOPPED" and result["recoveries_reserved"] == 1
    generate.assert_called_once()
    recover.assert_called_once()
    # Even an interrupted helper that left no recovery DB row cannot be paid again.
    recover.reset_mock()
    supervisor.run(work=tmp_path, generate=generate, recover=recover)
    recover.assert_not_called()


def test_distinct_key_limit_and_repeat_key_limit(tmp_path):
    """Bound the lifetime number of recovery reservations and reject duplicate keys."""
    failed_review(tmp_path, 28)
    failed_review(tmp_path, 29)
    generate = Mock(side_effect=[report(28), report(29)])
    recover = Mock(side_effect=recovered)
    result = supervisor.run(work=tmp_path, generate=generate, recover=recover, max_recoveries=1)
    assert result["status"] == "STOPPED" and result["recoveries_reserved"] == 1
    assert recover.call_count == 1


def test_generation_exception_never_recovers(tmp_path):
    """Preflight/credential/provider exceptions stop without recovery or retry."""
    generate, recover = Mock(side_effect=ValueError("budget")), Mock()
    assert supervisor.run(work=tmp_path, generate=generate, recover=recover)["status"] == "STOPPED"
    generate.assert_called_once()
    recover.assert_not_called()


def test_invalid_limit_and_audit_tamper_prevent_calls(tmp_path):
    """Neither a raised lifetime cap nor a changed audit can start generation."""
    generate, recover = Mock(), Mock()
    with pytest.raises(ValueError):
        supervisor.run(work=tmp_path, generate=generate, recover=recover, max_recoveries=101)
    generate.assert_not_called()
    supervisor.run(work=tmp_path, generate=Mock(return_value=report(status="QUALITY_STOP")), recover=recover)
    path = next((tmp_path / "supervisor_attempts").glob("event-*.json"))
    value = json.loads(path.read_text(encoding="utf-8"))
    value["data"] = {"tampered": True}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="audit hash"):
        supervisor.run(work=tmp_path, generate=generate, recover=recover)
    generate.assert_not_called()
