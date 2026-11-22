"""Offline calibration orchestration and frozen-provenance tests; no API access.

Purpose: enforce ten frozen probes, label isolation and pre-provider input checks.
Parameters: pytest temporary directories and monkeypatches. Returns: assertions.
Failures: expose regression without reading real credentials or invoking an SDK.
"""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import calibrate_independent_validator as calibration
from scripts import run_research_book as runner
from src.orchestration.independent_review import (
    build_payload, canonical_hash, contract_hash, verify_fixture_provenance, validate_review,
)


def write_json(path, value):
    """Purpose: write a synthetic local fixture. Parameters: path and JSON value.
    Returns: None. Failures: filesystem or serialization errors propagate.
    """
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def frozen_manifest(tmp_path):
    """Purpose: freeze ten probes with real provenance hashes. Parameters: tmp_path.
    Returns: fixture document/path and plan/revision paths. Failures: invalid setup.
    """
    fixtures = []
    for number in range(10):
        draft = {"id": str(number), "number": number + 1, "title_mr": "विचार",
                 "new_sutra": "उद्यमेन विवेकः", "exposition": ["विचार " * 500],
                 "references": [], "examples": [], "summary_mr": "विचार", "action_mr": "कृती"}
        comparisons = [] if number < 4 else [{
            "id": "prior", "formula": draft["new_sutra"],
            "decision_mr": "विचार", "action_mr": "कृती",
        }]
        fixtures.append({
            "id": f"case{number}", "draft": draft,
            "sources": {"references": [], "examples": []},
            "comparators": comparisons,
            "expected": {"outcome": "READY" if number < 4 else "REVISION_REQUIRED",
                         "required_categories": [] if number < 4 else ["EXACT_COPY"]},
            "reason": "EVALUATOR_ONLY_LABEL_DO_NOT_SEND",
        })
    plan = tmp_path / "plan.json"
    revisions = tmp_path / "revision_candidates_v2.json"
    write_json(plan, {"entries": [{"number": f["draft"]["number"]} for f in fixtures]})
    write_json(revisions, {"candidates": []})
    document = {
        "version": "validator-calibration-v2", "fixtures": fixtures,
        "manifest": {
            "contract_sha256": contract_hash(),
            "fixture_set_sha256": canonical_hash(fixtures),
            "input_sha256": {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (plan, revisions)},
            "payload_sha256": {f["id"]: canonical_hash(build_payload(f["draft"], f["sources"], f["comparators"]))
                               for f in fixtures},
            "expected_ready": 4, "expected_revision_required": 6,
        },
    }
    path = tmp_path / "validator_calibration_v2.json"
    write_json(path, document)
    verify_fixture_provenance(document, tmp_path)
    return SimpleNamespace(document=document, path=path, plan=plan, revisions=revisions)


def test_registry_blocks_every_nonvalidator_role():
    """Purpose: isolate calibration to the fifth role. Parameters: none.
    Returns: None. Failures: a writer/researcher/other role reaches the adapter.
    """
    registry = calibration.ValidatorRegistry(SimpleNamespace(provider_name="openai", model_id="gpt-4o"))
    for role in ("sutrakar_master", "bharatiya_jnana_specialist", "shandilya_specialist", "narada_specialist"):
        with pytest.raises(ValueError, match="Only independent_validator"):
            registry.get_adapter(role)


@pytest.fixture
def completed_calibration(tmp_path, monkeypatch, frozen_manifest):
    """Purpose: produce a genuine PASS report through ten fake adapter calls.
    Parameters: local fixture, tmp_path, monkeypatch. Returns: result/call capture.
    Failures: wrong provider settings or leaked labels fail before any SDK access.
    """
    monkeypatch.setattr(calibration, "WORK", tmp_path)
    monkeypatch.setattr(runner, "WORK", tmp_path)
    original_read = Path.read_text

    def safe_read(path, *args, **kwargs):
        """Purpose: substitute only the OpenAI key. Parameters: path/read options.
        Returns: fake key or fixture text. Failures: any other credential lookup.
        """
        if path.name == "openai_key.txt":
            return "synthetic-offline-key"
        if path.name.lower().endswith("_key.txt") or path.name == "claude_workspace_id.txt":
            raise AssertionError("Calibration must not read other provider credentials")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", safe_read)
    prompts = []

    class Adapter:
        """Fake GPT-4o adapter; real local dispatcher accounting, no SDK or sockets."""

        provider_name = "openai"
        model_id = "gpt-4o"
        max_tokens = 3000

        def __init__(self, **kwargs):
            """Purpose: verify frozen construction. Parameters: adapter options.
            Returns: None. Failures: changed model or token budget fails assertions.
            """
            assert kwargs["model_id"] == "gpt-4o" and kwargs["max_tokens"] == 3000
            assert kwargs["api_key"] == "synthetic-offline-key"

        def estimate_tokens(self, text):
            """Purpose: give deterministic local cost. Parameters: prompt text.
            Returns: 20 estimated tokens. Failures: none; no external token service.
            """
            return 20

        def generate(self, prompt, system_prompt):
            """Purpose: synthesize evidence-based results. Parameters: prompts.
            Returns: fake provider response. Failures: leaked evaluator labels.
            """
            prompts.append(prompt)
            assert '"expected"' not in prompt and "required_categories" not in prompt
            assert "EVALUATOR_ONLY_LABEL_DO_NOT_SEND" not in prompt
            assert '"manifest"' not in prompt and "expected_ready" not in prompt
            data = json.loads(prompt.split("\nEVIDENCE\n", 1)[1])
            assert data["00_review_checks"]["formula_word_count"] == 2
            issues = []
            if data["comparison_chapters"]:
                catalog = data["evidence_selection"]["catalog"]
                formula_ref = next(key for key, row in catalog.items()
                                   if row["kind"] == "draft" and row["field"] == "new_sutra")
                issues = [{"category": "EXACT_COPY", "draft_ref": formula_ref,
                           "reason": "Exact same formula", "evidence": {"comparator_id": "prior"}}]
            assert data["00_review_checks"]["source_claim_pairs"] == []
            decision_checks = {card["id"]: "EXACT_COPY" for card in data["comparison_chapters"]}
            answer = {"decision_checks": decision_checks,
                      "source_checks": [], "outcome": "REVISION_REQUIRED" if issues else "READY",
                      "blocking_issues": issues, "advisory_notes": [], "uncertainties": []}
            return SimpleNamespace(content=json.dumps(answer), was_truncated=False, provider="openai",
                model_id="gpt-4o", finish_reason="stop", usage=SimpleNamespace(input_tokens=20,
                  output_tokens=20, total_tokens=40, actual_cost_usd=None))

    monkeypatch.setattr(calibration, "OpenAIAdapter", Adapter)
    result = calibration.run(frozen_manifest.path, "validator-calibration-offline")
    assert result["status"] == "PASS" and result["calls"] == 10
    return SimpleNamespace(result=result, prompts=prompts)


def test_full_calibration_uses_only_validator_and_excludes_expected_labels(
        tmp_path, frozen_manifest, completed_calibration):
    """Purpose: exercise real dispatch/cache/evaluation with ten fake responses.
    Parameters: local fixtures. Returns: None. Failures: wrong roles, report hashes,
    label leakage or repeated calls when replaying exact evidence fail assertions.
    """
    result, prompts = completed_calibration.result, completed_calibration.prompts
    assert result["status"] == "PASS" and result["calls"] == 10
    assert result["claude_audit_calls"] == 0
    assert all(row["observed"]["source_checks"] == [] for row in result["results"])
    assert len(result["results"]) == len({row["id"] for row in result["results"]}) == 10
    assert {row["id"] for row in result["results"]} == {f["id"] for f in frozen_manifest.document["fixtures"]}
    assert sum(row["observed"]["outcome"] == "READY" for row in result["results"]) == 4
    assert result["fixture_sha256"] == canonical_hash(frozen_manifest.document)
    assert result["implementation_sha256"] == calibration.implementation_hash()
    assert all(row["evidence_selections"] == [] for row in result["results"][:4])
    assert all(row["evidence_selections"] for row in result["results"][4:])
    assert all(row["decision_comparisons"] == {} for row in result["results"][:4])
    assert all(row["decision_comparisons"] == {"prior": "EXACT_COPY"} for row in result["results"][4:])
    assert result["revision_candidates_sha256"] == hashlib.sha256(frozen_manifest.revisions.read_bytes()).hexdigest()
    approved = json.loads((tmp_path / "validator-calibration-approved.json").read_text(encoding="utf-8"))
    assert approved == result
    with sqlite3.connect(tmp_path / "dispatch.db") as db:
        audit = [json.loads(raw) for (raw,) in db.execute("SELECT record_json FROM council_dispatch_audit")]
    assert len(audit) == 10
    assert all(row["role"] == "independent_validator" and row["provider"] == "openai" for row in audit)

    # Exact review checkpoints survive a new billing run without another dispatch.
    replay = calibration.run(frozen_manifest.path, "validator-calibration-offline-replay")
    assert replay["status"] == "PASS" and replay["calls"] == 0 and len(prompts) == 10
    assert replay["reservation_usd"] == 0
    assert [r["review_key"] for r in replay["results"]] == [r["review_key"] for r in result["results"]]
    assert [r["evidence_selections"] for r in replay["results"]] == [r["evidence_selections"] for r in result["results"]]
    assert [r["decision_comparisons"] for r in replay["results"]] == [r["decision_comparisons"] for r in result["results"]]


@pytest.mark.parametrize("mutation,match", [
    ("plan", "Frozen calibration input changed"),
    ("revision", "Frozen calibration input changed"),
    ("missing_plan", "provenance is incomplete"),
    ("missing_revision", "provenance is incomplete"),
    ("fixture", "fixture hash changed"),
    ("payload", "model payload changed"),
    ("contract", "contract or fixture hash changed"),
    ("eight_fixtures", "Exactly ten unique"),
    ("duplicate_id", "Exactly ten unique"),
    ("outside_input", "outside project evidence directory"),
])
def test_provenance_mutation_stops_before_credentials_or_dispatch(
        tmp_path, monkeypatch, frozen_manifest, mutation, match):
    """Purpose: reject stale/incomplete calibration evidence before spending.
    Parameters: frozen manifest, mutation and pytest fixtures. Returns: None.
    Failures: changed input reaches credential loading, adapter creation or audit.
    """
    document = frozen_manifest.document
    manifest = document["manifest"]
    if mutation == "plan":
        write_json(frozen_manifest.plan, {"entries": [], "changed": True})
    elif mutation == "revision":
        write_json(frozen_manifest.revisions, {"candidates": [], "changed": True})
    elif mutation in {"missing_plan", "missing_revision"}:
        removed = frozen_manifest.plan if mutation == "missing_plan" else frozen_manifest.revisions
        del manifest["input_sha256"][str(removed.resolve())]
    elif mutation == "fixture":
        document["fixtures"][0]["reason"] += " altered evaluator label"
    elif mutation == "payload":
        document["fixtures"][0]["draft"]["title_mr"] = "बदललेला विषय"
        # A resealed fixture set cannot conceal a stale per-prompt evidence hash.
        manifest["fixture_set_sha256"] = canonical_hash(document["fixtures"])
    elif mutation == "contract":
        manifest["contract_sha256"] = "0" * 64
    elif mutation == "eight_fixtures":
        document["fixtures"] = document["fixtures"][:8]
    elif mutation == "duplicate_id":
        document["fixtures"][-1]["id"] = document["fixtures"][0]["id"]
    elif mutation == "outside_input":
        manifest["input_sha256"][str(tmp_path.parent / "outside-evidence.json")] = "0" * 64
    write_json(frozen_manifest.path, document)
    monkeypatch.setattr(calibration, "WORK", tmp_path)
    original_read = Path.read_text
    credential_reads = []

    def no_credentials(path, *args, **kwargs):
        """Purpose: forbid key access on invalid inputs. Parameters: read arguments.
        Returns: local fixture text. Failures: any credential read fails this test.
        """
        if path.name.lower().endswith("_key.txt") or path.name == "claude_workspace_id.txt":
            credential_reads.append(path.name)
            raise AssertionError("Provenance rejection must precede credential loading")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", no_credentials)
    adapter = Mock(side_effect=AssertionError("Invalid provenance must not initialize providers"))
    monkeypatch.setattr(calibration, "OpenAIAdapter", adapter)
    with pytest.raises(ValueError, match=match):
        calibration.run(frozen_manifest.path, "validator-calibration-invalid")
    adapter.assert_not_called()
    assert credential_reads == []
    assert not (tmp_path / "dispatch.db").exists()
    assert not (tmp_path / "independent_review_v2.db").exists()
    assert not (tmp_path / "validator-calibration-approved.json").exists()


def test_archived_entry_provenance_is_only_allowed_for_production_resume(tmp_path, frozen_manifest):
    """Purpose: preserve immutable entry history without weakening calibration.
    Parameters: tmp_path and frozen manifest. Returns: None. Failures: calibration
    accepts a changed live entry, or production cannot verify its exact archive.
    """
    entry = tmp_path / "entry-001.json"
    original = b'{"draft":"frozen-original"}'
    entry.write_bytes(original)
    document = frozen_manifest.document
    document["manifest"]["input_sha256"][str(entry.resolve())] = hashlib.sha256(original).hexdigest()
    archive = tmp_path / "pre_v2_results"
    archive.mkdir()
    (archive / entry.name).write_bytes(original)
    entry.write_bytes(b'{"draft":"current-reviewed"}')
    with pytest.raises(ValueError, match="Frozen calibration input changed"):
        verify_fixture_provenance(document, tmp_path)
    assert verify_fixture_provenance(document, tmp_path, allow_archived_entries=True) is None
    (archive / entry.name).write_bytes(b'{"draft":"wrong-history"}')
    with pytest.raises(ValueError, match="Frozen calibration input changed"):
        verify_fixture_provenance(document, tmp_path, allow_archived_entries=True)



def test_production_gate_accepts_genuine_passing_fake_calibration(
        tmp_path, frozen_manifest, completed_calibration):
    """Purpose: prove the real gate accepts the real fake-calibration report.
    Parameters: isolated WORK/fixture/report. Returns: None. Failures: producer and
    consumer disagree on approval filename, provenance, hashes or result identities.
    """
    assert runner.WORK == calibration.WORK == tmp_path
    approved_path = runner.WORK / "validator-calibration-approved.json"
    assert approved_path.is_file()
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    assert approved == completed_calibration.result
    assert runner.require_validator_calibration(runner.WORK) == approved
    assert approved["fixture_sha256"] == canonical_hash(frozen_manifest.document)
    assert len(approved["results"]) == 10
    assert len(completed_calibration.prompts) == 10


@pytest.mark.parametrize("mutation,match", [
    ("duplicate_fixture_ids", "Exactly ten unique"),
    ("duplicate_result_ids", "has not passed"),
    ("unmatched_result_id", "has not passed"),
    ("report_implementation_hash", "implementation or corrected candidates changed"),
    ("current_implementation_changed", "implementation or corrected candidates changed"),
    ("current_resolver_changed", "implementation or corrected candidates changed"),
])
def test_production_gate_rejects_mutated_approval_evidence(
        tmp_path, monkeypatch, frozen_manifest, completed_calibration, mutation, match):
    """Purpose: reject stale implementation or invalid fixture/result identities.
    Parameters: genuine fake-calibration output and mutation. Returns: None.
    Failures: tampered approval passes or gate checking triggers another call.
    """
    assert runner.require_validator_calibration(runner.WORK) == completed_calibration.result
    approved_path = runner.WORK / "validator-calibration-approved.json"
    report = json.loads(approved_path.read_text(encoding="utf-8"))
    if mutation == "duplicate_fixture_ids":
        document = frozen_manifest.document
        document["fixtures"][-1]["id"] = document["fixtures"][0]["id"]
        # Reseal content hashes so duplicate identity itself must cause rejection.
        document["manifest"]["fixture_set_sha256"] = canonical_hash(document["fixtures"])
        document["manifest"]["payload_sha256"] = {
            f["id"]: canonical_hash(build_payload(f["draft"], f["sources"], f["comparators"]))
            for f in document["fixtures"]
        }
        report["fixture_sha256"] = canonical_hash(document)
        write_json(frozen_manifest.path, document)
    elif mutation == "duplicate_result_ids":
        report["results"][-1]["id"] = report["results"][0]["id"]
        assert len(report["results"]) == 10
    elif mutation == "unmatched_result_id":
        report["results"][-1]["id"] = "not-a-frozen-fixture"
        assert len({r["id"] for r in report["results"]}) == 10
    elif mutation == "report_implementation_hash":
        report["implementation_sha256"] = "0" * 64
    elif mutation in {"current_implementation_changed", "current_resolver_changed"}:
        # The production identity covers BOTH files; mutate temporary copies only.
        from src.orchestration import independent_review
        temporary_root = tmp_path / "synthetic_project"
        implementation = temporary_root / "src/orchestration/independent_review.py"
        implementation.parent.mkdir(parents=True)
        source_root = Path(independent_review.__file__).resolve().parent
        for name in ("independent_review.py", "review_evidence.py"):
            content = (source_root / name).read_bytes()
            target = "independent_review.py" if mutation == "current_implementation_changed" else "review_evidence.py"
            if name == target:
                content += b"\n# synthetic changed implementation\n"
            (implementation.parent / name).write_bytes(content)
        monkeypatch.setattr(independent_review, "__file__", str(implementation))
    write_json(approved_path, report)
    with pytest.raises(ValueError, match=match):
        runner.require_validator_calibration(runner.WORK)
    assert len(completed_calibration.prompts) == 10



@pytest.mark.parametrize("run_id", [
    "offline-calibration", "Validator-calibration-case", "", None, 42,
    "validator-calibration-../escape", "validator-calibration-bad space",
    "validator-calibration-bad$",
])
def test_public_calibration_rejects_unsafe_or_unaccounted_ids(tmp_path, monkeypatch, run_id):
    """Purpose: prevent cumulative-cap prefix bypass. Parameters: unsafe run ID.
    Returns: None. Failures: invalid ID creates files or reaches internal/provider work.
    """
    work = tmp_path / "must-not-be-created"
    monkeypatch.setattr(calibration, "WORK", work)
    internal = Mock(side_effect=AssertionError("Invalid IDs must stop before calibration"))
    adapter = Mock(side_effect=AssertionError("No provider may be initialized"))
    monkeypatch.setattr(calibration, "_run", internal)
    monkeypatch.setattr(calibration, "OpenAIAdapter", adapter)
    with pytest.raises(ValueError, match="must start with validator-calibration-"):
        calibration.run(work / "unused-fixtures.json", run_id)
    internal.assert_not_called()
    adapter.assert_not_called()
    assert not work.exists()


def test_public_calibration_rejects_an_existing_execution_lock(tmp_path, monkeypatch):
    """Purpose: reject another process's active budget window. Parameters: fixtures.
    Returns: None. Failures: held SQLite lock permits internal/provider work.
    """
    monkeypatch.setattr(calibration, "WORK", tmp_path)
    internal = Mock(return_value={"status": "FAKE_COMPLETED"})
    adapter = Mock(side_effect=AssertionError("No provider may be initialized"))
    monkeypatch.setattr(calibration, "_run", internal)
    monkeypatch.setattr(calibration, "OpenAIAdapter", adapter)
    lock = sqlite3.connect(tmp_path / "calibration_execution_lock.db", timeout=0)
    try:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            calibration.run(tmp_path / "unused-fixtures.json", "validator-calibration-contender")
        internal.assert_not_called()
        adapter.assert_not_called()
    finally:
        lock.rollback()
        lock.close()
    result = calibration.run(tmp_path / "unused-fixtures.json", "validator-calibration-after-release", cap=.5)
    assert result == {"status": "FAKE_COMPLETED"}
    internal.assert_called_once_with(tmp_path / "unused-fixtures.json", "validator-calibration-after-release", .5)
    adapter.assert_not_called()


def test_simultaneous_public_calibrations_cannot_enter_same_budget_window(tmp_path, monkeypatch):
    """Purpose: exercise concurrent public entry points. Parameters: pytest fixtures.
    Returns: None. Failures: two internal runs overlap or the lock is held too briefly.
    """
    monkeypatch.setattr(calibration, "WORK", tmp_path)
    entered, release = Event(), Event()
    calls = []

    def held_internal(fixture_path, run_id, cap):
        """Purpose: hold the first fake run inside its lock. Parameters: run inputs.
        Returns: fake result. Failures: bounded wait expires; no SDK is initialized.
        """
        calls.append(run_id)
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("Fake calibration was not released")
        return {"status": "FAKE_COMPLETED"}

    monkeypatch.setattr(calibration, "_run", held_internal)
    adapter = Mock(side_effect=AssertionError("No provider may be initialized"))
    monkeypatch.setattr(calibration, "OpenAIAdapter", adapter)
    path = tmp_path / "unused-fixtures.json"
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(calibration.run, path, "validator-calibration-first")
        try:
            assert entered.wait(timeout=5), "First fake run did not enter the lock"
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                calibration.run(path, "validator-calibration-second")
            assert calls == ["validator-calibration-first"]
        finally:
            release.set()
        assert first.result(timeout=5) == {"status": "FAKE_COMPLETED"}
    adapter.assert_not_called()


def test_execution_lock_releases_after_internal_failure(tmp_path, monkeypatch):
    """Purpose: avoid a stuck calibration lock after exceptions. Parameters: fixtures.
    Returns: None. Failures: an internal failure prevents a later guarded attempt.
    """
    monkeypatch.setattr(calibration, "WORK", tmp_path)
    internal = Mock(side_effect=[RuntimeError("Synthetic internal failure"), {"status": "FAKE_COMPLETED"}])
    monkeypatch.setattr(calibration, "_run", internal)
    adapter = Mock(side_effect=AssertionError("No provider may be initialized"))
    monkeypatch.setattr(calibration, "OpenAIAdapter", adapter)
    path = tmp_path / "unused-fixtures.json"
    with pytest.raises(RuntimeError, match="Synthetic internal failure"):
        calibration.run(path, "validator-calibration-failed")
    assert calibration.run(path, "validator-calibration-after-failure") == {"status": "FAKE_COMPLETED"}
    assert internal.call_count == 2
    adapter.assert_not_called()



@pytest.mark.parametrize("rule,expected_pass", [("word_limit", False), ("character_limit", True)])
def test_calibration_requires_the_target_mechanical_rule(rule, expected_pass):
    """Purpose: distinguish a valid wrong-rule objection from the target probe.
    Parameters: observed rule and expected match. Returns: None. Failures: any
    MECHANICAL category is accepted despite a different expected evidence.rule.
    """
    draft = {"new_sutra": "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं विवेकं प्रमाणं कुर्यात्",
             "exposition": ["विचार " * 500], "comparative_mr": []}
    payload = build_payload(draft, {"references": [], "examples": []}, [])
    typed = {"source_checks": [], "outcome": "REVISION_REQUIRED", "advisory_notes": [], "uncertainties": [],
             "blocking_issues": [{"category": "MECHANICAL", "field": "new_sutra",
                 "quote": draft["new_sutra"], "reason": "Synthetic formula violates both limits.",
                 "evidence": {"rule": rule}}]}
    # Test scorer matching separately: v2.4 correctly rejects this incomplete
    # response at validation because both real limit violations must be reported.
    assert payload["00_review_checks"]["formula_word_count"] == 5
    assert payload["00_review_checks"]["formula_character_count"] > 32
    with pytest.raises(ValueError, match="omitted an objective limit violation"):
        validate_review(typed, payload)
    actual = {"typed_review": typed, "review_key": "synthetic-key",
              "reviewed_draft_sha256": canonical_hash(draft)}
    expected = {"outcome": "REVISION_REQUIRED", "required_categories": ["MECHANICAL"],
                "required_rules": ["character_limit"]}
    result = calibration.compare_result(actual, expected)
    assert result["pass"] is expected_pass
    assert result["observed"] == typed and result["expected"] == expected



def case_control_response(extra_grammar=False, uncertain=False):
    """Purpose: construct a schema-valid synthetic case-fact control response.
    Parameters: extra grammar/uncertainty flags. Returns: validated typed response
    and review metadata. Failures: invalid synthetic evidence fails validation.
    """
    canonical = {"case_id": "C1", "text_mr": "संस्थेने चाचणी केली."}
    draft = {"new_sutra": "उद्यमेन विवेकः", "exposition": ["विचार " * 500], "comparative_mr": [],
             "examples": [{"case_id": "C1", "text_mr": canonical["text_mr"] + " सर्व ग्राहकांचे उत्पन्न दुप्पट झाले."}]}
    issues = [{"category": "CASE_FACT", "field": "examples.0.text_mr", "quote": "सर्व ग्राहकांचे उत्पन्न दुप्पट झाले.",
               "reason": "Synthetic case claim absent from the supplied facts.",
               "evidence": {"case_id": "C1", "canonical_quote": canonical["text_mr"],
                            "contradiction": "The canonical case does not describe doubled customer income."}}]
    if extra_grammar:
        issues.append({"category": "GRAMMAR", "field": "new_sutra", "quote": draft["new_sutra"],
                       "reason": "Additional synthetic grammar complaint.",
                       "evidence": {"rule": "Synthetic agreement rule", "explanation": "Synthetic rule application."}})
    uncertainties = [{"category": "LEXICAL_AMBIGUITY", "field": "new_sutra", "quote": draft["new_sutra"],
                      "question": "Which sense of विवेकः is intended in this sentence?"}] if uncertain else []
    typed = {"source_checks": [], "outcome": "REVISION_REQUIRED", "blocking_issues": issues,
             "advisory_notes": [], "uncertainties": uncertainties}
    assert validate_review(typed, build_payload(draft, {"references": [], "examples": [canonical]}, [])) == typed
    return {"typed_review": typed, "review_key": "synthetic-case-control", "reviewed_draft_sha256": canonical_hash(draft)}


@pytest.mark.parametrize("extra_grammar,expected_pass", [(False, True), (True, False)])
def test_case_fact_control_rejects_extra_grammar_category(extra_grammar, expected_pass):
    """Purpose: require exact category agreement, not a subset match.
    Parameters: extra blocker and expected result. Returns: None. Failures:
    the expected CASE_FACT finding hides a spurious additional GRAMMAR finding.
    """
    actual = case_control_response(extra_grammar=extra_grammar)
    expected = {"outcome": "REVISION_REQUIRED", "required_categories": ["CASE_FACT"]}
    result = calibration.compare_result(actual, expected)
    assert result["pass"] is expected_pass
    assert result["observed"] == actual["typed_review"]


@pytest.mark.parametrize("uncertain,expected_pass", [(False, True), (True, False)])
def test_negative_control_rejects_uncertainty_even_with_exact_expected_defect(uncertain, expected_pass):
    """Purpose: fail uncertainty on negative controls too. Parameters: uncertainty flag.
    Returns: None. Failures: matching defect/outcome conceals an unresolved question.
    """
    actual = case_control_response(uncertain=uncertain)
    expected = {"outcome": "REVISION_REQUIRED", "required_categories": ["CASE_FACT"]}
    result = calibration.compare_result(actual, expected)
    assert result["pass"] is expected_pass


@pytest.mark.parametrize("uncertain", [False, True])
def test_positive_control_requires_ready_without_uncertainty(uncertain):
    """Purpose: retain strict positive-control readiness. Parameters: uncertainty flag.
    Returns: None. Failures: a held but otherwise clean chapter counts as positive PASS.
    """
    draft = {"new_sutra": "उद्यमेन विवेकः", "exposition": ["विचार " * 500], "comparative_mr": []}
    questions = [{"category": "LEXICAL_AMBIGUITY", "field": "new_sutra", "quote": draft["new_sutra"],
                  "question": "Which sense of विवेकः is intended here?"}] if uncertain else []
    typed = {"source_checks": [], "outcome": "AUTHOR_REVIEW" if uncertain else "READY", "blocking_issues": [],
             "advisory_notes": ["Optional style suggestion."], "uncertainties": questions}
    assert validate_review(typed, build_payload(draft, {"references": [], "examples": []}, [])) == typed
    actual = {"typed_review": typed, "review_key": "synthetic-positive", "reviewed_draft_sha256": canonical_hash(draft)}
    assert calibration.compare_result(actual, {"outcome": "READY", "required_categories": []})["pass"] is (not uncertain)


@pytest.mark.parametrize("observed_rules,expected_pass", [
    (["character_limit"], True),
    (["character_limit", "word_limit"], False),
    (["word_limit"], False),
])
def test_mechanical_control_requires_exact_rule_set_without_extras(observed_rules, expected_pass):
    """Purpose: require exactly the planted mechanical rule set. Parameters: rules.
    Returns: None. Failures: a second valid rule hides behind the requested rule.
    """
    draft = {"new_sutra": "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं विवेकं प्रमाणं कुर्यात्",
             "exposition": ["विचार " * 500], "comparative_mr": []}
    typed = {"source_checks": [], "outcome": "REVISION_REQUIRED", "advisory_notes": [], "uncertainties": [],
             "blocking_issues": [{"category": "MECHANICAL", "field": "new_sutra", "quote": draft["new_sutra"],
                 "reason": "Synthetic formula violates both mechanical limits.", "evidence": {"rule": rule}}
                 for rule in observed_rules]}
    payload = build_payload(draft, {"references": [], "examples": []}, [])
    if set(observed_rules) == {"character_limit", "word_limit"}:
        assert validate_review(typed, payload) == typed
    else:
        with pytest.raises(ValueError, match="omitted an objective limit violation"):
            validate_review(typed, payload)
    # The scorer still rejects extra/wrong target rules independently of validation.
    actual = {"typed_review": typed, "review_key": "synthetic-rule-set", "reviewed_draft_sha256": canonical_hash(draft)}
    expected = {"outcome": "REVISION_REQUIRED", "required_categories": ["MECHANICAL"], "required_rules": ["character_limit"]}
    assert calibration.compare_result(actual, expected)["pass"] is expected_pass



@pytest.fixture
def calibration_ledger():
    """Purpose: create only an in-memory budget ledger with the authorized baseline.
    Parameters: none. Returns: yielded SQLite connection. Failures: SQL errors;
    no real billing ledger, credential, provider or filesystem is accessed.
    """
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE council_dispatch_audit (run_id TEXT NOT NULL, reservation_usd REAL NOT NULL)")
    db.executemany("INSERT INTO council_dispatch_audit VALUES (?,?)",
                   [("validator-calibration-v2", .04)] * 8 + [("validator-calibration-v22", .0926475)])
    try:
        yield db
    finally:
        db.close()


@pytest.mark.parametrize("run_id", ["validator-calibration-v23", "validator-calibration-v24"])
@pytest.mark.parametrize("reserved_v23,reserved_v24,projected,allowed", [
    (.313, 0., .05, True),
    (.313, .68, .007, True),
    (.313, .687, .00001, False),
    (.313, .69, .001, False),
])
def test_fixed_analogy_round_shares_one_dollar_across_exact_ids(
        calibration_ledger, run_id, reserved_v23, reserved_v24, projected, allowed):
    """Purpose: bound the exact v23/v24 phase to one combined dollar.
    Parameters: in-memory ledger, two spends and projected reservation. Returns:
    None. Failures: either ID gets a fresh cap or calls continue after exhaustion.
    """
    assert calibration.ANALOGY_ROUND_IDS == ("validator-calibration-v23", "validator-calibration-v24")
    db = calibration_ledger
    db.executemany("INSERT INTO council_dispatch_audit VALUES (?,?)",
                   [("validator-calibration-v23", reserved_v23), ("validator-calibration-v24", reserved_v24)])
    if allowed:
        assert calibration.check_calibration_reservation(db, run_id, projected) is None
    else:
        with pytest.raises(RuntimeError, match=r"combined \$1 reservation"):
            calibration.check_calibration_reservation(db, run_id, projected)


@pytest.mark.parametrize("mutation", ["count_eight", "count_ten_same_sum", "sum_higher", "sum_lower", "absent"])
def test_analogy_round_rejects_changed_historical_baseline(calibration_ledger, mutation):
    """Purpose: bind the allowance to exactly nine prior calls totaling .4126475.
    Parameters: ledger and mutation. Returns: None. Failures: changed prior count
    or spend grants the extra scoped phase allowance.
    """
    db = calibration_ledger
    if mutation == "count_eight":
        db.execute("DELETE FROM council_dispatch_audit WHERE rowid=1")
    elif mutation == "count_ten_same_sum":
        db.execute("INSERT INTO council_dispatch_audit VALUES ('validator-calibration-extra',0)")
    elif mutation == "sum_higher":
        db.execute("UPDATE council_dispatch_audit SET reservation_usd=reservation_usd+.001 WHERE rowid=1")
    elif mutation == "sum_lower":
        db.execute("UPDATE council_dispatch_audit SET reservation_usd=reservation_usd-.001 WHERE rowid=1")
    else:
        db.execute("DELETE FROM council_dispatch_audit")
    with pytest.raises(RuntimeError, match="recorded nine-call baseline"):
        calibration.check_calibration_reservation(db, "validator-calibration-v24", .001)


@pytest.mark.parametrize("run_id", [
    "validator-calibration-v250", "validator-calibration-v230", "validator-calibration-v24-retry",
    "validator-calibration-arbitrary", "validator-calibration-offline",
])
def test_arbitrary_prefixed_id_does_not_receive_new_phase_allowance(calibration_ledger, run_id):
    """Purpose: deny a fresh dollar to arbitrary otherwise-safe run IDs.
    Parameters: in-memory ledger and run ID. Returns: None. Failures: prefix alone
    grants the exact v23/v24 allowance or ignores their existing reservations.
    """
    db = calibration_ledger
    db.execute("INSERT INTO council_dispatch_audit VALUES ('validator-calibration-v23',.6)")
    # The exact authorized phase has room, but other IDs retain the old cumulative cap.
    assert calibration.check_calibration_reservation(db, "validator-calibration-v24", .01) is None
    with pytest.raises(RuntimeError, match=r"Cumulative \$1"):
        calibration.check_calibration_reservation(db, run_id, .01)


def test_other_ids_retain_original_cumulative_limit(calibration_ledger):
    """Purpose: preserve the unchanged original cap for ordinary calibration IDs.
    Parameters: baseline ledger. Returns: None. Failures: ordinary IDs gain a cap
    increase or an allowed below-cap projection is rejected.
    """
    db = calibration_ledger
    assert calibration.check_calibration_reservation(db, "validator-calibration-ordinary", .1) is None
    with pytest.raises(RuntimeError, match=r"Cumulative \$1"):
        calibration.check_calibration_reservation(db, "validator-calibration-ordinary", .6)


@pytest.fixture
def evidence_round_ledger():
    """Purpose: model the 21-call/$1.04303 history without touching billing files.
    Parameters: none. Returns: in-memory SQLite connection. Failures: SQL setup;
    the nine-call and twelve-call subtotals retain their real phase totals.
    """
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE council_dispatch_audit (run_id TEXT NOT NULL, reservation_usd REAL NOT NULL)")
    rows = ([("validator-calibration-v2", .364395 / 8)] * 8 +
            [("validator-calibration-v22", .0482525)] +
            [("validator-calibration-v23", .3133725 / 6)] * 6 +
            [("validator-calibration-v24", .31701 / 6)] * 6)
    db.executemany("INSERT INTO council_dispatch_audit VALUES (?,?)", rows)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.parametrize("spent,projected,allowed", [
    (0., .5, True), (0., 1., True), (.4, .6, True),
    (.4, .60001, False), (1., .00001, False), (1.01, .001, False),
])
def test_v25_exact_round_has_one_dollar_without_erasing_history(
        evidence_round_ledger, spent, projected, allowed):
    """Purpose: reserve v25 against one shared fixed dollar across resumptions.
    Parameters: prior spend/projection. Returns: None. Failures: renewed caps,
    changed historical rows or exceeding the evidence-round allowance.
    """
    db = evidence_round_ledger
    assert calibration.EVIDENCE_ROUND_ID == "validator-calibration-v25"
    count, historical = db.execute("SELECT COUNT(*),SUM(reservation_usd) FROM council_dispatch_audit").fetchone()
    assert count == 21 and historical == pytest.approx(1.04303, abs=1e-12)
    db.execute("INSERT INTO council_dispatch_audit VALUES (?,?)", (calibration.EVIDENCE_ROUND_ID, spent))
    before = db.execute("SELECT rowid,* FROM council_dispatch_audit").fetchall()
    if allowed:
        assert calibration.check_calibration_reservation(db, calibration.EVIDENCE_ROUND_ID, projected) is None
    else:
        with pytest.raises(RuntimeError, match=r"v25 exceeds its fixed \$1"):
            calibration.check_calibration_reservation(db, calibration.EVIDENCE_ROUND_ID, projected)
    assert db.execute("SELECT rowid,* FROM council_dispatch_audit").fetchall() == before


@pytest.mark.parametrize("mutation", ["count20", "count22_same_sum", "higher", "lower", "absent"])
def test_v25_rejects_changed_21_call_baseline(evidence_round_ledger, mutation):
    """Purpose: reject stale historical count or spend, even with ample new cap.
    Parameters: synthetic ledger mutation. Returns: None; failures identify a
    guard that silently grants the new authorization against different history.
    """
    db = evidence_round_ledger
    if mutation == "count20":
        db.execute("DELETE FROM council_dispatch_audit WHERE rowid=1")
    elif mutation == "count22_same_sum":
        db.execute("INSERT INTO council_dispatch_audit VALUES ('validator-calibration-extra',0)")
    elif mutation in {"higher", "lower"}:
        db.execute("UPDATE council_dispatch_audit SET reservation_usd=reservation_usd+? WHERE rowid=1",
                   (.00001 if mutation == "higher" else -.00001,))
    else:
        db.execute("DELETE FROM council_dispatch_audit")
    with pytest.raises(RuntimeError, match="recorded 21-call"):
        calibration.check_calibration_reservation(db, calibration.EVIDENCE_ROUND_ID, .01)


def test_v25_cannot_start_from_old_nine_call_baseline(calibration_ledger):
    """Purpose: keep new authorization bound to the completed prior rounds.
    Parameters: old baseline ledger. Returns: None; premature v25 access fails.
    """
    with pytest.raises(RuntimeError, match="recorded 21-call"):
        calibration.check_calibration_reservation(calibration_ledger, calibration.EVIDENCE_ROUND_ID, .01)


@pytest.mark.parametrize("run_id", ["validator-calibration-v250", "validator-calibration-v25-retry",
                                     "validator-calibration-v260", "validator-calibration-arbitrary"])
def test_evidence_allowance_does_not_extend_to_other_ids(evidence_round_ledger, run_id):
    """Purpose: prevent arbitrary aliases from obtaining the v25 allowance.
    Parameters: unauthorized prefixed ID. Returns: None; cumulative guard holds.
    """
    with pytest.raises(RuntimeError, match=r"Cumulative \$1"):
        calibration.check_calibration_reservation(evidence_round_ledger, run_id, .01)


@pytest.fixture
def decision_round_ledger(evidence_round_ledger):
    """Extend only the in-memory baseline by ten v25 calls totaling $.6623475.
    Params: previous-round fixture. Return: 31-call ledger; SQL failures propagate.
    """
    evidence_round_ledger.executemany("INSERT INTO council_dispatch_audit VALUES (?,?)",
                                    [("validator-calibration-v25", .6623475 / 10)] * 10)
    return evidence_round_ledger


@pytest.mark.parametrize("spent,projected,allowed", [
    (0., .5, True), (0., 1., True), (.4, .6, True),
    (.4, .60001, False), (1., .00001, False), (1.01, .001, False),
])
def test_v26_exact_round_has_one_fixed_dollar(decision_round_ledger, spent, projected, allowed):
    """Bound v26 and resumed v26 reservations without changing historical rows.
    Params: fake ledger/spend/projection. Return: assertions; overspending fails.
    """
    db = decision_round_ledger
    assert calibration.DECISION_ROUND_ID == "validator-calibration-v26"
    count, historical = db.execute("SELECT COUNT(*),SUM(reservation_usd) FROM council_dispatch_audit").fetchone()
    assert count == 31 and historical == pytest.approx(1.7053775, abs=1e-12)
    db.execute("INSERT INTO council_dispatch_audit VALUES (?,?)", (calibration.DECISION_ROUND_ID, spent))
    before = db.execute("SELECT rowid,* FROM council_dispatch_audit").fetchall()
    if allowed:
        assert calibration.check_calibration_reservation(db, calibration.DECISION_ROUND_ID, projected) is None
    else:
        with pytest.raises(RuntimeError, match=r"v26 exceeds its fixed \$1"):
            calibration.check_calibration_reservation(db, calibration.DECISION_ROUND_ID, projected)
    assert db.execute("SELECT rowid,* FROM council_dispatch_audit").fetchall() == before


@pytest.mark.parametrize("mutation", ["count30", "count32_same_sum", "higher", "lower", "absent"])
def test_v26_rejects_changed_31_call_baseline(decision_round_ledger, mutation):
    """Require the exact 31-call/$1.7053775 baseline before using new authority.
    Params: fake ledger and change. Return: assertions; changed history fails.
    """
    db = decision_round_ledger
    if mutation == "count30":
        db.execute("DELETE FROM council_dispatch_audit WHERE rowid=1")
    elif mutation == "count32_same_sum":
        db.execute("INSERT INTO council_dispatch_audit VALUES ('validator-calibration-extra',0)")
    elif mutation in {"higher", "lower"}:
        db.execute("UPDATE council_dispatch_audit SET reservation_usd=reservation_usd+? WHERE rowid=1",
                   (.00001 if mutation == "higher" else -.00001,))
    else:
        db.execute("DELETE FROM council_dispatch_audit")
    with pytest.raises(RuntimeError, match="recorded 31-call"):
        calibration.check_calibration_reservation(db, calibration.DECISION_ROUND_ID, .01)


def test_v26_cannot_start_from_old_21_call_baseline(evidence_round_ledger):
    """Reject premature v26 use. Param: old fake history. Return: assertions."""
    with pytest.raises(RuntimeError, match="recorded 31-call"):
        calibration.check_calibration_reservation(evidence_round_ledger, calibration.DECISION_ROUND_ID, .01)


@pytest.mark.parametrize("run_id", ["validator-calibration-v260", "validator-calibration-v26-retry",
                                     "validator-calibration-v27", "validator-calibration-arbitrary"])
def test_decision_allowance_does_not_extend_to_other_ids(decision_round_ledger, run_id):
    """Reject unauthorized aliases. Params: fake ledger/ID. Return: assertions."""
    with pytest.raises(RuntimeError, match=r"Cumulative \$1"):
        calibration.check_calibration_reservation(decision_round_ledger, run_id, .01)
