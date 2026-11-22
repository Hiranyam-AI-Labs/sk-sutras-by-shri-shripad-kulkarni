"""Offline calibration checks with synthetic drafts, never paid model calls."""
from copy import deepcopy
import json

import pytest

from scripts import prepare_validator_calibration as calibration
from src.orchestration.research_acceptance import assess_research_entry, _devanagari_word


@pytest.fixture
def inputs():
    """Return valid mock drafts/packets/priors; assertions diagnose mock failures."""
    drafts, packets = {}, {}
    for number, formula in ((1, "ग्राहकव्यथां पृष्ट्वा परीक्षेत"),
                            (5, "विमतं पृष्ट्वा मार्गान् पश्येत्"),
                            (8, "पर्याप्तसाक्ष्ये निश्चिनुयात्"),
                            (9, "सविकल्पं दायित्वं वहेत्")):
        ref = dict(id="CMP008", title="On Liberty", author="John Stuart Mill",
            locator="Chapter II", original_text="Discussion and experience.",
            meaning_mr="चर्चा आणि अनुभव", url="https://example.org/source", tradition="Western")
        cases = [dict(case_id=f"OLD-{number}-{kind}", kind=kind, entity=f"Company {number} {kind}",
            text_mr="अचूक पुरवलेला प्रसंग", url=f"https://example.org/{number}/{kind}",
            source_title="Fixture evidence") for kind in ("positive", "caution")]
        packets[number] = {"references": [ref], "examples": cases}
        drafts[number] = dict(id=f"NEW-{number:03}", number=number, chapter=1,
            title_mr="दृष्टीचा विस्तार", new_sutra=formula, grammar_mr="व्याकरण विवेचन",
            translation_mr="अर्थ समजावा", exposition=[" ".join(["उद्योग"] * 505)],
            references=["CMP008"], comparative_mr=[dict(source_id="CMP008", explanation_mr="मूळ अर्थ आणि मर्यादित उपमा")],
            examples=deepcopy(cases), case_ids=[c["case_id"] for c in cases],
            dos_mr=["तपास करा"] * 3, donts_mr=["घाई टाळा"] * 3,
            application_mr="उपयोग समजावा", action_mr=f"कृती {number} ठरवा", summary_mr=f"निर्णय {number} घ्या")
    return drafts, packets, [deepcopy(drafts[1])]


def write(path, value):
    """Write temporary test JSON; I/O errors propagate, no workspace input writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def workspace(tmp_path, inputs):
    """Make a mock source directory from inputs; return path for prepare tests."""
    drafts, packets, _ = inputs
    work = tmp_path / "logs" / "calibration"
    rows = []
    for number, draft in drafts.items():
        rows.append({**{k: draft[k] for k in ("id", "number", "chapter", "title_mr")},
                     "source_packet": packets[number], "source_packet_sha256": calibration.digest(packets[number])})
        write(work / f"entry-{number:03}.json", {"draft": draft,
            "status": "READY_FOR_AUTHOR_REVIEW" if number == 1 else "NEEDS_REVIEW",
            "assessment": {"status": "PASS"}, "review": {"verdict": "PASS" if number == 1 else "REVIEW_REQUIRED"}})
    write(work / "plan.json", {"entries": rows})
    write(work / "revision_candidates_v2.json", {"candidates": [{"draft": drafts[n]} for n in (5, 8, 9)]})
    write(work / "editorial_corrections.json", {"NEW-001": [{"field": "application_mr",
        "old": "उपयोग समजावा", "new": "मर्यादित उपयोग समजावा", "reason": "test overlay"}]})
    return work


def test_balanced_ten_fixtures_preserve_inputs_and_sources(inputs):
    before = deepcopy(inputs)
    fixtures = calibration.build_fixtures(*inputs)
    assert len(fixtures) == 10
    assert [f["expected"]["outcome"] for f in fixtures].count("READY") == 4
    assert inputs == before
    for f in fixtures:
        assert set(f) == {"id", "draft", "sources", "comparators", "expected", "reason"}
        assert f["sources"] == inputs[1][f["draft"]["number"]]
        for c in f["comparators"]:
            assert set(c) == {"id", "formula", "decision_mr", "action_mr"}


def test_model_input_cannot_leak_expected_reason_or_metadata(inputs):
    fixture = calibration.build_fixtures(*inputs)[0]
    fixture.update(expected={"outcome": "SECRET_LABEL"}, reason="SECRET_REASON", extra="SECRET_EXTRA")
    fixture["draft"]["peer_review"] = "SECRET_PEER_OPINION"
    fixture["sources"]["expected"] = "SECRET_SOURCE_LABEL"
    payload = calibration.model_input(fixture)
    assert set(payload) == {"00_review_checks", "current_draft", "canonical_sources", "comparison_chapters", "current_business_decision", "classical_source_policy", "historical_formula_policy", "evidence_selection", "decision_comparisons"}
    assert "SECRET_" not in json.dumps(payload)
    payload["current_draft"]["summary_mr"] = "mutated"
    assert fixture["draft"]["summary_mr"] != "mutated"


def test_nested_metadata_is_removed_without_changing_evidence_payload(inputs):
    """Nested evaluator opinions must neither leak nor change the clean payload."""
    fixture = calibration.build_fixtures(*inputs)[4]
    clean_payload = calibration.model_input(fixture)
    rows = [fixture["sources"]["references"][0], fixture["sources"]["examples"][0],
            fixture["draft"]["comparative_mr"][0], fixture["draft"]["examples"][0],
            fixture["comparators"][0]]
    for row in rows:
        row.update(expected={"outcome": "SECRET_READY"}, prior_review="SECRET_REVIEW",
                   reason="SECRET_REASON", metadata={"label": "SECRET_LABEL"})
    before = deepcopy(fixture)
    payload = calibration.model_input(fixture)
    assert payload == clean_payload
    assert "SECRET_" not in json.dumps(payload)
    assert fixture == before


def test_four_words_are_inclusive_and_title_wording_not_mandated(inputs):
    fixture = calibration.build_fixtures(*inputs)[1]
    assert len(fixture["draft"]["new_sutra"].split()) == 4
    assert fixture["draft"]["title_mr"] not in fixture["draft"]["new_sutra"]
    assert fixture["expected"] == {"outcome": "READY", "required_categories": []}
    assert assess_research_entry(fixture["draft"], fixture["sources"], [], [], set())["status"] == "PASS"
    assert "Four words is within the 2-4 word limit" in calibration.RUBRIC
    assert "modern operational application need not occur literally" in calibration.RUBRIC


@pytest.mark.parametrize("index,category,issue", [
    (4, "EXACT_COPY", "Normalized duplicate"),
    (6, "CASE_FACT", "text_mr"),
    (7, "MECHANICAL", "32 characters"),
    (8, "MECHANICAL", "499 Devanagari"),
])
def test_mechanical_negative_has_required_failure(inputs, index, category, issue):
    f = calibration.build_fixtures(*inputs)[index]
    result = assess_research_entry(f["draft"], f["sources"],
        [c["formula"] for c in f["comparators"]], [], set())
    assert f["expected"]["required_categories"] == [category]
    assert result["status"] == "NEEDS_REVISION"
    assert any(issue in x for x in result["issues"])


def test_short_prose_exactly_499_script_words(inputs):
    f = calibration.build_fixtures(*inputs)[8]
    assert sum(_devanagari_word(t) for p in f["draft"]["exposition"] for t in p.split()) == 499
    assert f["expected"]["required_rules"] == ["exposition_minimum"]
    assert calibration.build_fixtures(*inputs)[7]["expected"]["required_rules"] == ["character_limit"]


def test_all_categories_and_hashes_use_authoritative_contract(tmp_path, inputs):
    from src.orchestration.independent_review import canonical_hash, contract_hash
    result = calibration.prepare(workspace(tmp_path, inputs))
    allowed = {"EXACT_COPY", "SOURCE_DISTORTION", "CASE_FACT", "MECHANICAL",
               "DUPLICATE_DECISION", "GRAMMAR", "UNSUPPORTED_CLAIM"}
    for f in result["fixtures"]:
        assert set(f["expected"]["required_categories"]) <= allowed
        assert result["manifest"]["payload_sha256"][f["id"]] == canonical_hash(calibration.model_input(f))
    assert result["manifest"]["fixture_set_sha256"] == canonical_hash(result["fixtures"])
    assert result["manifest"]["contract_sha256"] == contract_hash()


def test_manifest_provenance_is_usable_for_parent_stale_hash_gate(tmp_path, inputs):
    """Manifest uses path->raw-byte SHA256 and ID->canonical payload SHA256."""
    import hashlib
    from pathlib import Path
    work = workspace(tmp_path, inputs)
    result = calibration.prepare(work)
    manifest = result["manifest"]
    ids = [f["id"] for f in result["fixtures"]]
    assert len(ids) == len(set(ids)) == 10
    assert set(manifest["payload_sha256"]) == set(ids)
    assert str(work / "revision_candidates_v2.json") in manifest["input_sha256"]
    for path, expected in manifest["input_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    candidate_path = work / "revision_candidates_v2.json"
    candidate_path.write_bytes(candidate_path.read_bytes() + b"\n")
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest() != manifest["input_sha256"][str(candidate_path)]


def test_relative_work_path_retains_absolute_provenance_keys(tmp_path, inputs, monkeypatch):
    """Equivalent CLI path spellings must not produce a spurious stale manifest."""
    work = workspace(tmp_path, inputs)
    expected = calibration.prepare(work)
    monkeypatch.chdir(tmp_path)
    assert calibration.prepare(work.relative_to(tmp_path)) == expected


def test_v22_deterministic_checks_use_actual_fixture_text(inputs):
    fixtures = calibration.build_fixtures(*inputs)
    assert calibration.model_input(fixtures[1])["00_review_checks"]["formula_word_count"] == 4
    assert calibration.model_input(fixtures[4])["00_review_checks"]["exact_formula_matches"] == ["PRIOR-001"]
    pairs = calibration.model_input(fixtures[5])["00_review_checks"]["source_claim_pairs"]
    assert pairs[0]["current_claim"] == fixtures[5]["draft"]["comparative_mr"][0]["explanation_mr"]
    assert pairs[0]["original_text"] == fixtures[5]["sources"]["references"][0]["original_text"]
    cases = calibration.model_input(fixtures[6])["00_review_checks"]["case_fact_pairs"]
    assert cases[0]["changed_fields"] == ["text_mr"]
    assert calibration.model_input(fixtures[7])["00_review_checks"]["formula_character_count"] > 32
    assert calibration.model_input(fixtures[8])["00_review_checks"]["exposition_word_count"] == 499


def test_attribution_negative_keeps_known_source_and_only_changes_comparison(inputs):
    f = calibration.build_fixtures(*inputs)[5]
    assert f["draft"]["comparative_mr"][0]["source_id"] == "CMP008"
    assert f["sources"] == inputs[1][1]
    assert {k for k in f["draft"] if f["draft"][k] != inputs[0][1][k]} == {"comparative_mr"}
    assert f["expected"]["required_categories"] == ["SOURCE_DISTORTION"]


def test_real_decision_duplicate_is_not_only_exact_formula_repetition(inputs):
    f = calibration.build_fixtures(*inputs)[9]
    c = f["comparators"][0]
    assert c["formula"] != f["draft"]["new_sutra"]
    assert c["decision_mr"] == f["draft"]["summary_mr"]
    assert c["action_mr"] == f["draft"]["action_mr"]
    assert f["expected"]["required_categories"] == ["DUPLICATE_DECISION"]
    assert assess_research_entry(f["draft"], f["sources"], [c["formula"]], [], set())["status"] == "PASS"


def test_prepare_applies_baseline_overlay_and_freezes_inputs(tmp_path, inputs):
    work = workspace(tmp_path, inputs)
    before = {p: p.read_bytes() for p in work.iterdir()}
    result = calibration.prepare(work)
    assert result["fixtures"][0]["draft"]["application_mr"] == "मर्यादित उपयोग समजावा"
    assert result["manifest"]["planned_calls"] == 10
    assert result["manifest"]["calls_performed"] == 0
    assert calibration.prepare(work) == result
    assert {p: p.read_bytes() for p in work.iterdir()} == before


def test_missing_chandra_file_fails_without_output(tmp_path, inputs):
    work = workspace(tmp_path, inputs)
    (work / "revision_candidates_v2.json").unlink()
    with pytest.raises(FileNotFoundError):
        calibration.prepare(work)
    assert not (work / "validator_calibration_v2.json").exists()


def test_actual_number_keyed_chandra_format_and_provenance(tmp_path, inputs):
    work = workspace(tmp_path, inputs)
    value = {str(n): {"draft": inputs[0][n], "rationale": "AUTHOR_REVIEW_PENDING",
        "edits": [], "source_draft_sha256": calibration.digest(inputs[0][n])} for n in (5, 8, 9)}
    write(work / "revision_candidates_v2.json", value)
    assert set(calibration.revised_drafts(value)) == {5, 8, 9}
    assert len(calibration.prepare(work)["fixtures"]) == 10
    value["5"]["source_draft_sha256"] = "stale"
    write(work / "revision_candidates_v2.json", value)
    with pytest.raises(ValueError, match="source draft hash"):
        calibration.prepare(work)


def test_number_key_must_match_draft_identity(inputs):
    with pytest.raises(ValueError, match="identity"):
        calibration.revised_drafts({"5": {"draft": inputs[0][8]}})


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "identity", "case", "packet"])
def test_invalid_revision_inputs_fail_closed(tmp_path, inputs, mutation):
    work = workspace(tmp_path, inputs)
    path = work / "revision_candidates_v2.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "duplicate":
        value["candidates"].append(deepcopy(value["candidates"][0]))
    elif mutation == "missing":
        value["candidates"].pop()
    elif mutation == "identity":
        value["candidates"][0]["draft"]["title_mr"] = "दुसरे शीर्षक"
    elif mutation == "case":
        value["candidates"][0]["draft"]["examples"][0]["text_mr"] = "बदललेला प्रसंग"
    else:
        plan_path = work / "plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["entries"][0]["source_packet_sha256"] = "bad"
        write(plan_path, plan)
    write(path, value)
    with pytest.raises(ValueError):
        calibration.prepare(work)


def test_cli_writes_only_new_calibration_file_and_refuses_overwrite(tmp_path, inputs, monkeypatch):
    work = workspace(tmp_path, inputs)
    monkeypatch.setattr(calibration, "ROOT", tmp_path)
    output = work / "validator_calibration_v2.json"
    assert calibration.main(["--work-dir", str(work), "--output", str(output)]) == 0
    frozen = output.read_bytes()
    with pytest.raises(SystemExit):
        calibration.main(["--work-dir", str(work), "--output", str(output)])
    assert output.read_bytes() == frozen
    with pytest.raises(SystemExit):
        calibration.main(["--work-dir", str(work), "--output", str(work / "plan.json")])
