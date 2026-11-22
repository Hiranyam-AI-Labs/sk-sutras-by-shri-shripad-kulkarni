"""Focused offline audit tests; synthetic evidence lives only in pytest tmp_path."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import audit_research_book as audit
from scripts import export_research_book as exporter
from src.orchestration.independent_review import canonical_hash


def write(path, value):
    """Write synthetic JSON. Params: path/value. Return: None; I/O errors surface."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def edit(path, change):
    """Edit a fixture through a callable. Return: None; malformed edits fail visibly."""
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    write(path, value)


def packet_hash(packet):
    """Return canonical fixture hash; non-JSON fixture values fail serialization."""
    return hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def make_book(tmp_path, refs=("CLASSIC", "CLASSIC")):
    """Create a small valid final-book fixture. Params: temp root and reference IDs.
    Return: work/cases paths. No network or real project writes; assertion paths
    in tests diagnose failures.
    """
    work, cases_dir = tmp_path / "work", tmp_path / "old"
    registry, plan, old_cases = {}, [], []
    formulas = ["उद्यमेन विवेकः", "ज्ञानं शक्तिः", "श्रमः आधारः"]
    names = [("Orchid Works", "Cobalt Systems"), ("Maple Ventures", "Nimbus Labs"),
             ("Quartz Works", "Aspen Care")]
    for index, ref_id in enumerate(refs):
        number = index + 1
        ref = dict(id=ref_id, title="Fixture source", author="Seneca", locator="Section 1",
                   original_text="अभ्यासेन ज्ञानम्", meaning_mr="मूळ अर्थ",
                   url="https://example.org/source", tradition="Western")
        registry[ref_id] = ref
        examples = []
        for kind, name in zip(("positive", "caution"), names[index]):
            original = dict(entry_id=f"OLD-{number:03}", kind=kind, entity=name,
                            text_mr="पुरवलेला अचूक प्रसंग", url=f"https://example.org/{number}/{kind}",
                            source_title="Original case evidence", aliases=[])
            old_cases.append(original)
            examples.append({"case_id": f"OLD-{number:03}-{kind}",
                             **{k: original[k] for k in ("kind", "entity", "text_mr", "url", "source_title")}})
        packet = {"references": [deepcopy(ref)], "examples": examples}
        plan.append(dict(id=f"NEW-{number:03}", number=number, chapter=1,
                         source_entry_id=f"OLD-{number:03}", source_packet=packet,
                         source_packet_sha256=packet_hash(packet)))
        draft = dict(id=f"NEW-{number:03}", number=number, chapter=1, title_mr="चाचणी विषय",
            new_sutra=formulas[index], grammar_mr="व्याकरण विवेचन", translation_mr="मराठी अर्थ",
            exposition=[(["उद्योग", "विवेक", "प्रयत्न"][index] + " ") * 500],
            references=[ref_id], comparative_mr=[{"source_id": ref_id, "explanation_mr": "सेनेका यांचे विवेचन"}],
            examples=deepcopy(examples), case_ids=[c["case_id"] for c in examples],
            dos_mr=["विचार करा", "तपास करा", "कृती करा"], donts_mr=["घाई टाळा", "लोभ टाळा", "विलंब टाळा"],
            application_mr="उपयोग समजावा", action_mr="पुढील कृती ठरवा", summary_mr="सारांश समजावा")
        write(work / f"entry-{number:03}.json", dict(draft=draft,
            status="READY_FOR_AUTHOR_REVIEW", assessment={"status": "PASS", "issues": []},
            review={"verdict": "PASS", "issues": []}))
    write(work / "plan.json", {"entries": plan, "chapters": [{"chapter": 1, "title": "चाचणी"}]})
    write(work / "source_catalog.json", {"references": list(registry.values())})
    write(work / "forbidden_formulas.json", ["अभ्यासेन ज्ञानम्", "सत्येन लाभः"])
    write(cases_dir / "cases-001-003.json", old_cases)
    return work, cases_dir


def run(paths, through=2):
    """Audit a fixture and return its report; no write or provider call."""
    return audit.audit_book(paths[0], through, paths[1])


def codes(report):
    """Return structural diagnostic codes for assertions; malformed reports fail."""
    return {e["code"] for e in report["errors"]}


def test_valid_overlay_is_applied_without_changing_inputs(tmp_path):
    paths = make_book(tmp_path)
    write(paths[0] / "editorial_corrections.json", {"NEW-001": [{
        "field": "application_mr", "old": "उपयोग समजावा", "new": "नेमका उपयोग समजावा", "reason": "clarity"}]})
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    report = run(paths)
    assert report["structural_status"] == "PASS" and report["author_approval"] == "PENDING"
    assert report["included"][0]["editorial_overlay_count"] == 1
    assert report["counts"]["case_ids"] == 4
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.parametrize("gate", ["status", "assessment", "review"])
def test_only_triple_pass_results_are_included(tmp_path, gate):
    paths = make_book(tmp_path)
    def change(result):
        if gate == "status":
            result["status"] = "NEEDS_REVISION"
        elif gate == "assessment":
            result["assessment"]["status"] = "NEEDS_REVISION"
        else:
            result["review"]["verdict"] = "REVIEW_REQUIRED"
    edit(paths[0] / "entry-001.json", change)
    report = run(paths)
    assert report["structural_status"] == "PASS"
    assert [e["id"] for e in report["included"]] == ["NEW-002"]
    assert report["numbering_map"][0]["display_number"] == 1


@pytest.mark.parametrize("field,value,fragment", [
    ("exposition", ["उद्योग " * 499 + "English 123"], "499 Devanagari"),
    ("new_sutra", "एक दोन तीन चार पाच", "two to four"),
    ("new_sutra", "॥ सत्येन, लाभः ॥", "forbidden_originals"),
    ("references", ["UNKNOWN"], "not in packet"),
    ("comparative_mr", [], "Missing comparison"),
    ("case_ids", ["wrong"], ""),
])
def test_structural_checks_reassess_saved_pass(tmp_path, field, value, fragment):
    paths = make_book(tmp_path)
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update({field: value}))
    report = run(paths)
    assert report["structural_status"] == "FAIL"
    if fragment:
        assert any(fragment in e.get("detail", "") for e in report["errors"])


@pytest.mark.parametrize("field", ["case_id", "kind", "entity", "text_mr", "url", "source_title"])
def test_every_canonical_case_field_is_exact(tmp_path, field):
    paths = make_book(tmp_path)
    edit(paths[0] / "entry-001.json", lambda d: d["draft"]["examples"][0].update({field: "changed"}))
    report = run(paths)
    assert report["structural_status"] == "FAIL"
    assert "entry_acceptance" in codes(report)


def test_case_ledger_catches_coordinated_packet_and_draft_change(tmp_path):
    paths = make_book(tmp_path)
    def change(plan):
        row = plan["entries"][0]
        row["source_packet"]["examples"][0]["text_mr"] = "बदललेला प्रसंग"
        row["source_packet_sha256"] = packet_hash(row["source_packet"])
    edit(paths[0] / "plan.json", change)
    edit(paths[0] / "entry-001.json", lambda d: d["draft"]["examples"][0].update(text_mr="बदललेला प्रसंग"))
    assert any("old case ledger" in e.get("detail", "") for e in run(paths)["errors"])


def test_duplicate_formula_and_entity_are_structural_failures(tmp_path):
    paths = make_book(tmp_path)
    edit(paths[0] / "entry-002.json", lambda d: d["draft"].update(new_sutra="॥ उद्यमेन विवेकः ॥"))
    report = run(paths)
    assert any("prior_formulas" in e.get("detail", "") for e in report["errors"])
    # Keep every evidence layer consistent: duplicate business identity is still invalid.
    def change_plan(plan):
        row = plan["entries"][1]
        row["source_packet"]["examples"][0]["entity"] = "Orchid Works"
        row["source_packet_sha256"] = packet_hash(row["source_packet"])
    edit(paths[0] / "plan.json", change_plan)
    edit(paths[0] / "entry-002.json", lambda d: d["draft"]["examples"][0].update(entity="Orchid Works"))
    edit(paths[1] / "cases-001-003.json", lambda rows: rows[2].update(entity="Orchid Works"))
    assert "duplicate_case_entity" in codes(run(paths))


def test_reference_ledger_and_forbidden_coverage_are_required(tmp_path):
    paths = make_book(tmp_path)
    edit(paths[0] / "source_catalog.json", lambda d: d["references"][0].update(original_text="वेगळा मूलपाठ"))
    report = run(paths)
    assert "source_line_not_forbidden" in codes(report)
    assert any("source ledger" in e.get("detail", "") for e in report["errors"])
    (paths[0] / "forbidden_formulas.json").unlink()
    assert "input_error" in codes(run(paths))


def test_forbidden_object_format_and_frozen_packet_hash(tmp_path):
    paths = make_book(tmp_path)
    write(paths[0] / "forbidden_formulas.json", {"formulas": ["अभ्यासेन ज्ञानम्", "सत्येन लाभः"]})
    assert run(paths)["structural_status"] == "PASS"
    edit(paths[0] / "plan.json", lambda d: d["entries"][0].update(source_packet_sha256="bad"))
    assert any("hash mismatch" in e.get("detail", "") for e in run(paths)["errors"])


@pytest.mark.parametrize("modern", ["CMP012", "CMP013", "CMP014"])
def test_modern_source_once_and_comparison_strictly_under_100(tmp_path, modern):
    paths = make_book(tmp_path, refs=(modern, modern))
    assert "modern_source_reused" in codes(run(paths))
    paths = make_book(tmp_path, refs=(modern, "CLASSIC"))
    edit(paths[0] / "entry-001.json", lambda d: d["draft"]["comparative_mr"][0].update(explanation_mr="विचार " * 99))
    assert run(paths)["structural_status"] == "PASS"
    edit(paths[0] / "entry-001.json", lambda d: d["draft"]["comparative_mr"][0].update(explanation_mr="विचार " * 100))
    assert "comparison_word_limit" in codes(run(paths))


def test_review_flags_do_not_reject_and_ignore_philosophers_short_labels(tmp_path):
    paths = make_book(tmp_path)
    edit(paths[1] / "cases-001-003.json",
         lambda rows: rows[2].update(aliases=["Maple Alias", "BP", "Apple", "Seneca", "इतर उद्योग"]))
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update(
        application_mr="Maple Alias आणि इतर उद्योग; BP Apple Seneca. Maple AliasPlus."))
    report = run(paths)
    assert report["structural_status"] == "PASS"
    mentions = [f["matched_alias"] for f in report["review_flags"] if f["code"] == "other_business_mention"]
    assert sorted(mentions) == sorted(["maple alias", "इतर उद्योग"])
    assert all(f["other_entry_ids"] == ["NEW-002"] for f in report["review_flags"])


def test_exact_long_paragraph_and_old_numbers_are_review_only(tmp_path):
    paths = make_book(tmp_path, refs=("CLASSIC", "CLASSIC", "CLASSIC"))
    edit(paths[0] / "entry-001.json", lambda d: d.update(status="NEEDS_REVISION"))
    shared = "सामायिक विचार " * 16
    for n in (2, 3):
        edit(paths[0] / f"entry-{n:03}.json", lambda d: d["draft"]["exposition"].append(shared))
    edit(paths[0] / "entry-003.json", lambda d: d["draft"].update(
        application_mr="उद्यम सूत्र २ पाहा. NEW-002 पहा. नारद सूत्र २ हा शास्त्रीय संदर्भ आहे."))
    report = run(paths, 3)
    assert report["structural_status"] == "PASS"
    flags = report["review_flags"]
    assert len([f for f in flags if f["code"] == "repeated_exposition_paragraph"]) == 1
    numbers = [f for f in flags if f["code"] == "possible_old_entry_number"]
    assert len(numbers) == 2 and all(f["display_number"] == 1 for f in numbers)


def test_trailing_exclusion_reference_is_flagged(tmp_path):
    paths = make_book(tmp_path)
    edit(paths[0] / "entry-002.json", lambda d: d.update(status="NEEDS_REVISION"))
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update(action_mr="सूत्र २ पाहा"))
    report = run(paths)
    assert report["structural_status"] == "PASS"
    assert any(f["code"] == "possible_old_entry_number" and f["display_number"] is None
               for f in report["review_flags"])


def test_missing_future_entry_is_final_incompleteness_not_generation_action(tmp_path):
    paths = make_book(tmp_path)
    (paths[0] / "entry-002.json").unlink()
    report = run(paths)
    assert report["structural_status"] == "FAIL"
    assert report["missing"] == [2] and "incomplete_final_range" in codes(report)
    assert "not a current generation gate" in report["scope"]


def test_invalid_overlay_fails_without_raw_mutation(tmp_path):
    paths = make_book(tmp_path)
    raw = (paths[0] / "entry-001.json").read_bytes()
    write(paths[0] / "editorial_corrections.json", {"NEW-001": [{
        "field": "examples.0.text_mr", "old": "प्रसंग", "new": "बदल", "reason": "not allowed"}]})
    assert "entry_error" in codes(run(paths))
    assert (paths[0] / "entry-001.json").read_bytes() == raw


def test_cli_report_only_and_no_overwrite(tmp_path, monkeypatch):
    paths = make_book(tmp_path)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    output = tmp_path / "logs" / "final-audit.json"
    argv = ["--through", "2", "--work-dir", str(paths[0]), "--cases-dir", str(paths[1]), "--output", str(output)]
    assert audit.main(argv) == 0
    saved = output.read_bytes()
    with pytest.raises(SystemExit):
        audit.main(argv)
    assert output.read_bytes() == saved
    with pytest.raises(SystemExit):
        audit.main(argv[:-1] + [str(tmp_path / "outside.json")])


def test_malformed_old_case_ledger_returns_json_failure(tmp_path):
    paths = make_book(tmp_path)
    edit(paths[1] / "cases-001-003.json", lambda rows: rows[0].pop("kind"))
    report = run(paths)
    assert report["structural_status"] == "FAIL" and "input_error" in codes(report)


def test_duplicate_case_ids_across_entries_fail_even_with_consistent_packets(tmp_path):
    paths = make_book(tmp_path)
    plan = json.loads((paths[0] / "plan.json").read_text(encoding="utf-8"))
    first = plan["entries"][0]
    second = plan["entries"][1]
    second["source_entry_id"] = first["source_entry_id"]
    second["source_packet"] = deepcopy(first["source_packet"])
    second["source_packet_sha256"] = first["source_packet_sha256"]
    write(paths[0] / "plan.json", plan)
    edit(paths[0] / "entry-002.json", lambda d: d["draft"].update(
        examples=deepcopy(second["source_packet"]["examples"]),
        case_ids=[c["case_id"] for c in second["source_packet"]["examples"]]))
    report = run(paths)
    assert report["structural_status"] == "FAIL"
    assert any("Case ID already used" in e.get("detail", "") for e in report["errors"])


@pytest.mark.parametrize("words,expected", [(29, False), (30, True)])
def test_repeated_paragraph_threshold_is_30_words(tmp_path, words, expected):
    paths = make_book(tmp_path)
    for number in (1, 2):
        edit(paths[0] / f"entry-{number:03}.json",
             lambda d: d["draft"]["exposition"].append("सामायिक " * words))
    report = run(paths)
    assert report["structural_status"] == "PASS"
    assert any(f["code"] == "repeated_exposition_paragraph" for f in report["review_flags"]) is expected


def bind_review(result):
    """Bind a fixture's current draft to a typed READY review; return None; malformed fixtures raise."""
    result["review"].update(typed_review={"outcome": "READY", "blocking_issues": [],
        "advisory_notes": [], "uncertainties": []},
        reviewed_draft_sha256=canonical_hash(result["draft"]), rubric_sha256="b" * 64)


def export_fixture(paths, monkeypatch):
    """Configure synthetic export evidence and capture renderer inputs without rendering.

    Params: work/cases paths and pytest monkeypatch. Return: captured call list.
    Assumes CMP008 exists; JSON fixture failures propagate. Real acceptance runs.
    """
    work = paths[0]
    edit(work / "source_catalog.json", lambda d: d.update(groups=[]))
    monkeypatch.setattr(exporter, "WORK", work)
    calls = []

    def capture(opening, closing, entries, chapters, references, output, catalog):
        """Capture renderer parameters for assertions; return synthetic report; no document I/O."""
        calls.append(deepcopy(entries))
        return {"main_entries": len(entries)}

    monkeypatch.setattr(exporter, "render_research_book", capture)
    return calls


def test_v2_audit_ignores_redundant_overlay_and_records_binding(tmp_path):
    """Audit pre-corrected bound prose; expect no second overlay and no input mutation."""
    paths = make_book(tmp_path)
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update(application_mr="नेमका उपयोग समजावा"))
    edit(paths[0] / "entry-001.json", bind_review)
    write(paths[0] / "editorial_corrections.json", {"NEW-001": [{
        "field": "application_mr", "old": "उपयोग समजावा", "new": "नेमका उपयोग समजावा", "reason": "clarity"}]})
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    report = run(paths)
    assert report["structural_status"] == "PASS"
    assert report["included"][0]["editorial_overlay_count"] == 0
    evidence = report["review_selections"]["NEW-001"]
    assert evidence["review_binding_verified"] and not evidence["post_review_prose_changed"]
    assert evidence["rubric_sha256"] == "b" * 64
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


def test_v2_mixed_export_records_only_actual_legacy_overlays(tmp_path, monkeypatch):
    """Export mixed review versions through a capture renderer; verify exact v2 prose and legacy changes."""
    paths = make_book(tmp_path, refs=("CMP008", "CMP008"))
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update(application_mr="नेमका उपयोग समजावा"))
    edit(paths[0] / "entry-001.json", bind_review)
    corrections = {sid: [{"field": "application_mr", "old": "उपयोग समजावा",
        "new": "नेमका उपयोग समजावा", "reason": "clarity"}] for sid in ("NEW-001", "NEW-002")}
    write(paths[0] / "editorial_corrections.json", corrections)
    calls = export_fixture(paths, monkeypatch)
    before = {p: p.read_bytes() for p in paths[0].glob("*.json")}
    report = exporter.export(tmp_path / "unused.docx", 2)
    assert len(calls) == 1
    assert calls[0][0] == json.loads(before[paths[0] / "entry-001.json"])["draft"]
    assert calls[0][1]["application_mr"] == "नेमका उपयोग समजावा"
    assert report["post_model_editorial_corrections"] == {"NEW-002": corrections["NEW-002"]}
    assert report["review_selections"]["NEW-001"]["editorial_overlay_count"] == 0
    assert report["review_selections"]["NEW-002"]["editorial_overlay_count"] == 1
    assert all(p.read_bytes() == data for p, data in before.items())


def test_v2_hash_mismatch_fails_audit_and_export_before_render(tmp_path, monkeypatch):
    """Tamper with saved reviewed prose; both consumers must fail and export must never render."""
    paths = make_book(tmp_path, refs=("CMP008", "CMP008"))
    edit(paths[0] / "entry-001.json", bind_review)
    edit(paths[0] / "entry-001.json", lambda d: d["draft"].update(application_mr="बदललेला अर्थ"))
    calls = export_fixture(paths, monkeypatch)
    report = run(paths)
    assert report["structural_status"] == "FAIL"
    assert any("reviewed draft hash mismatch" in e.get("detail", "") for e in report["errors"])
    with pytest.raises(ValueError, match="reviewed draft hash mismatch"):
        exporter.export(tmp_path / "unused.docx", 2, allow_exclusions=True)
    assert not calls and not (paths[0] / "export-2.json").exists()


def test_v2_held_entry_excluded_and_binding_precedes_display_number(tmp_path, monkeypatch):
    """Exclude a typed hold, renumber accepted copy only, and retain original reviewed hash in reports."""
    paths = make_book(tmp_path, refs=("CMP008", "CMP008"))
    for number in (1, 2):
        edit(paths[0] / f"entry-{number:03}.json", bind_review)

    def hold(result):
        """Mark a fixture uncertain; return None; fixture shape errors propagate."""
        result["status"] = "NEEDS_REVISION"
        result["review"]["verdict"] = "REVIEW_REQUIRED"
        result["review"]["typed_review"].update(outcome="AUTHOR_REVIEW", uncertainties=["तपास आवश्यक"])

    edit(paths[0] / "entry-001.json", hold)
    calls = export_fixture(paths, monkeypatch)
    raw = json.loads((paths[0] / "entry-002.json").read_text(encoding="utf-8"))
    audit_report = run(paths)
    assert audit_report["structural_status"] == "PASS"
    assert [e["id"] for e in audit_report["included"]] == ["NEW-002"]
    with pytest.raises(ValueError, match="unresolved"):
        exporter.export(tmp_path / "unused.docx", 2)
    report = exporter.export(tmp_path / "unused.docx", 2, allow_exclusions=True)
    assert [e["id"] for e in calls[0]] == ["NEW-002"]
    expected = deepcopy(raw["draft"])
    expected["number"] = 1
    assert calls[0][0] == expected
    assert report["review_selections"]["NEW-002"]["selected_draft_sha256"] == canonical_hash(raw["draft"])
    assert report["review_selections"] == audit_report["review_selections"]
    assert report["post_model_editorial_corrections"] == {}
    assert json.loads((paths[0] / "entry-002.json").read_text(encoding="utf-8")) == raw
