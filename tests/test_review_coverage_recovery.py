"""Offline 19-card coverage recovery tests; callbacks are mocks, never providers."""

import json
import sqlite3
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from src.orchestration import independent_review as review


@pytest.fixture
def failed(tmp_path):
    """Return a real failed cache with nineteen complete comparison cards.

    Parameters: pytest directory. Failures: setup must reproduce the exact
    diagnosed coverage error through the production reviewer and codec.
    """
    draft = {"id": "NEW-020", "number": 20, "title_mr": "विचार",
             "new_sutra": "उद्यमेन विवेकः", "exposition": ["विचार " * 500],
             "references": [], "examples": [], "summary_mr": "ग्राहकाची गरज समजून निर्णय घ्या",
             "action_mr": "प्रश्न विचारा आणि उत्तर तपासा"}
    sources = {"references": [], "examples": []}
    cards = [{"id": f"NEW-{n:03d}", "formula": f"पूर्व सूत्र {n}",
              "decision_mr": f"वेगळा निर्णय {n}", "action_mr": f"वेगळी कृती {n}"}
             for n in range(1, 20)]
    raw = {"decision_checks": {"NEW-001": "DISTINCT"}, "source_checks": [],
           "outcome": "READY", "blocking_issues": [], "advisory_notes": [], "uncertainties": []}
    path = tmp_path / "review.db"
    provider = Mock(return_value=deepcopy(raw))
    reviewer = review.IndependentReviewer(path, provider)
    with pytest.raises(RuntimeError, match="invalid or unavailable"):
        reviewer.review(draft, sources, cards)
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT review_key,state,request_json,response_json,error FROM independent_reviews_v2").fetchone()
    assert row[4] == review._COVERAGE_ERROR
    complete = deepcopy(raw)
    complete["decision_checks"] = {c["id"]: "DISTINCT" for c in cards}
    return {"path": path, "key": row[0], "original": row[1:], "draft": draft,
            "sources": sources, "cards": cards, "response": complete,
            "payload": review.build_payload(draft, sources, cards)}


def replay(case):
    """Replay production cache with a callback that fails if invoked; return result."""
    callback = Mock(side_effect=AssertionError("Replay must not spend"))
    result = review.IndependentReviewer(case["path"], callback).review(
        case["draft"], case["sources"], case["cards"])
    callback.assert_not_called()
    return result


def retained(case):
    """Read original state and bytes; return tuple for immutable-evidence assertions."""
    with sqlite3.connect(case["path"]) as db:
        return db.execute("SELECT state,request_json,response_json,error FROM independent_reviews_v2 WHERE review_key=?",
                          (case["key"],)).fetchone()


def test_one_complete_review_and_zero_call_replays(failed):
    """Require exact full prompt, durable pre-call reservation and all nineteen IDs."""
    case = failed

    def callback(system, prompt):
        """Inspect durable reservation and unchanged evidence, then return mock READY."""
        request = json.loads(case["original"][1])
        assert system == request["system"] == review.SYSTEM
        assert prompt.startswith(request["prompt"] + "\nCOVERAGE CORRECTION\n")
        correction = prompt.split("\nCOVERAGE CORRECTION\n")[1]
        assert "exactly 19" in correction
        assert json.dumps([c["id"] for c in case["cards"]]) in correction
        assert "READY" not in correction and "DISTINCT" not in correction
        with sqlite3.connect(case["path"]) as db:
            assert db.execute(f"SELECT state FROM {review._COVERAGE_TABLE}").fetchone() == ("RUNNING",)
        assert retained(case) == case["original"]
        return case["response"]

    call = Mock(side_effect=callback)
    record = review.recover_missing_decision_coverage(case["path"], case["key"], call)
    assert record["provider_calls"] == 1
    assert review.recover_missing_decision_coverage(case["path"], case["key"], call) == record
    assert call.call_count == 1
    result = replay(case)
    assert result["outcome"] == "READY" and len(result["decision_comparisons"]) == 19
    assert result["coverage_recovery"] == record
    assert retained(case) == case["original"]


def test_same_decision_rejects_original_ready(failed):
    """A full rereview may reject; evidence is resolved by the unchanged codec."""
    response = failed["response"]
    response["decision_checks"]["NEW-019"] = "SAME_DECISION"
    catalog = failed["payload"]["evidence_selection"]["catalog"]
    ref = next(k for k, row in catalog.items() if row["kind"] == "draft" and row["field"] == "summary_mr")
    response.update(outcome="REVISION_REQUIRED", blocking_issues=[{
        "category": "DUPLICATE_DECISION", "draft_ref": ref,
        "reason": "The same practical decision and action recur in NEW-019.",
        "evidence": {"comparator_id": "NEW-019"}}])
    review.recover_missing_decision_coverage(failed["path"], failed["key"], Mock(return_value=response))
    result = replay(failed)
    assert result["outcome"] == "REVISION_REQUIRED" and result["verdict"] == "REVIEW_REQUIRED"
    assert result["typed_review"]["blocking_issues"][0]["category"] == "DUPLICATE_DECISION"
    assert retained(failed) == failed["original"]


@pytest.mark.parametrize("defect", ["missing", "foreign", "same_without_blocker", "false_exact", "missing_field", "extra_field", "mechanical"])
def test_invalid_rereview_is_retained_and_never_retried(failed, defect):
    """Every full response must pass coverage, wire, objective and outcome checks."""
    response = failed["response"]
    if defect == "missing":
        del response["decision_checks"]["NEW-019"]
    elif defect == "foreign":
        response["decision_checks"]["NEW-999"] = response["decision_checks"].pop("NEW-019")
    elif defect == "same_without_blocker":
        response["decision_checks"]["NEW-019"] = "SAME_DECISION"
    elif defect == "false_exact":
        response["decision_checks"]["NEW-019"] = "EXACT_COPY"
    elif defect == "missing_field":
        del response["source_checks"]
    elif defect == "extra_field":
        response["extra"] = True
    else:
        response["outcome"] = "REVISION_REQUIRED"  # No corresponding substantive blocker.
    call = Mock(return_value=response)
    with pytest.raises(RuntimeError, match="Coverage rereview failed"):
        review.recover_missing_decision_coverage(failed["path"], failed["key"], call)
    with sqlite3.connect(failed["path"]) as db:
        state, raw, error = db.execute(f"SELECT state,response_json,error FROM {review._COVERAGE_TABLE}").fetchone()
    assert state == "FAILED" and json.loads(raw) == response and error
    for operation in (lambda: review.recover_missing_decision_coverage(failed["path"], failed["key"], call), lambda: replay(failed)):
        with pytest.raises(RuntimeError, match="no automatic retry"):
            operation()
    assert call.call_count == 1 and retained(failed) == failed["original"]


@pytest.mark.parametrize("error", [ValueError("provider failed"), KeyboardInterrupt()])
def test_provider_failure_or_interruption_cannot_retry(failed, error):
    """Ordinary failure is FAILED; interrupted work stays RUNNING and blocks replay."""
    call = Mock(side_effect=error)
    with pytest.raises((RuntimeError, KeyboardInterrupt)):
        review.recover_missing_decision_coverage(failed["path"], failed["key"], call)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.recover_missing_decision_coverage(failed["path"], failed["key"], call)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        replay(failed)
    assert call.call_count == 1 and retained(failed) == failed["original"]


@pytest.mark.parametrize("defect", ["other_error", "complete", "foreign_id", "invalid_relation", "all_ids", "request_prompt", "request_hash"])
def test_ineligible_original_never_calls(failed, defect):
    """Only the exact diagnosed failure with an intact original request is eligible."""
    state, request_json, raw_json, error = failed["original"]
    request, raw = json.loads(request_json), json.loads(raw_json)
    if defect == "other_error":
        error = "ValueError: Different failure"
    elif defect == "complete":
        state = "COMPLETE"
    elif defect == "foreign_id":
        raw["decision_checks"] = {"foreign": "DISTINCT"}
    elif defect == "invalid_relation":
        raw["decision_checks"]["NEW-001"] = "UNKNOWN"
    elif defect == "all_ids":
        raw = failed["response"]
    elif defect == "request_prompt":
        request["prompt"] += "changed"
    else:
        request["contract_hash"] = "changed"
    with sqlite3.connect(failed["path"]) as db:
        db.execute("UPDATE independent_reviews_v2 SET state=?,request_json=?,response_json=?,error=?",
                   (state, json.dumps(request), json.dumps(raw), error))
    call = Mock()
    with pytest.raises(ValueError):
        review.recover_missing_decision_coverage(failed["path"], failed["key"], call)
    call.assert_not_called()


@pytest.mark.parametrize("target", ["original_raw", "original_request", "retry_prompt", "raw", "metadata", "error", "state", "implementation"])
def test_replay_rejects_tampering(failed, target, monkeypatch):
    """Bind retained bytes, request, output, status, metadata and implementation."""
    review.recover_missing_decision_coverage(failed["path"], failed["key"], Mock(return_value=failed["response"]))
    with sqlite3.connect(failed["path"]) as db:
        if target.startswith("original_"):
            column = "response_json" if target == "original_raw" else "request_json"
            db.execute(f"UPDATE independent_reviews_v2 SET {column}={column} || ' '")
        elif target in ("retry_prompt", "raw", "metadata"):
            column = {"retry_prompt": "request_json", "raw": "response_json", "metadata": "record_json"}[target]
            value = json.loads(db.execute(f"SELECT {column} FROM {review._COVERAGE_TABLE}").fetchone()[0])
            if target == "retry_prompt":
                value["prompt"] += "changed"
            elif target == "raw":
                value["advisory_notes"] = ["Altered after completion"]
            else:
                value["provider_calls"] = 0
            db.execute(f"UPDATE {review._COVERAGE_TABLE} SET {column}=?", (json.dumps(value),))
        elif target == "implementation":
            monkeypatch.setattr(review, "implementation_hash", lambda: "changed")
        else:
            db.execute(f"UPDATE {review._COVERAGE_TABLE} SET {target}=?", ("FAILED" if target == "state" else "changed",))
    with pytest.raises((RuntimeError, ValueError)):
        replay(failed)


def test_simultaneous_explicit_recovery_calls_only_once(failed):
    """A durable RUNNING reservation excludes a concurrent second paid callback."""
    entered, release = Event(), Event()

    def callback(system, prompt):
        """Hold the first mock call until the competing recovery has been rejected."""
        entered.set()
        assert release.wait(10)
        return failed["response"]

    call = Mock(side_effect=callback)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(review.recover_missing_decision_coverage, failed["path"], failed["key"], call)
        try:
            assert entered.wait(10)
            with pytest.raises(RuntimeError, match="no automatic retry"):
                review.recover_missing_decision_coverage(failed["path"], failed["key"], call)
        finally:
            release.set()
        first.result(timeout=10)
    assert call.call_count == 1
    assert replay(failed)["outcome"] == "READY"
