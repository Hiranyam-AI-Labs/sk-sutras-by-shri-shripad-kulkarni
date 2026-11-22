"""Synthetic mapping and mocked export tests; never render a real DOCX or call APIs."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from scripts import export_source_first_book as exporter
from src.orchestration.independent_review import canonical_hash


@pytest.fixture
def registry():
    return {"fixture-ref": {
        "id": "fixture-ref", "title": "Fixture title", "author": "Fixture author",
        "locator": "fixture locator", "original_text": "EXISTING TEST TEXT ONLY",
        "meaning_mr": "चाचणी अर्थ", "url": "https://example.org/fixture",
        "tradition": "Other",
    }}


def ready(number=17, stage="opening"):
    """Create local synthetic final results, including opaque content to preserve."""
    draft = {
        "id": f"fixture-{number}", "number": number, "chapter": 97,
        "title_mr": "चाचणी", "new_sutra": f"EXISTING_FIXTURE_{number}",
        "grammar_mr": "विवरण", "translation_mr": "अर्थ",
        "exposition": ["line 1\nline 2", "e\u0301\u00a0 unchanged  spacing"],
        "references": ["fixture-ref"],
        "comparative_mr": [{"source_id": "fixture-ref", "explanation_mr": "संबंध"}],
        "examples": [{"case_id": f"fixture-case-{number}", "text_mr": "मूळ मजकूर",
                      "kind": "positive", "entity": "Fixture", "url": "https://example.org",
                      "source_title": "Fixture title"}],
        "application_mr": "उपयोग", "action_mr": "कृती", "summary_mr": "सार",
        "opaque_future_field": {"nested": [None, True, 3.5, {"a": "बदलू नये"}]},
    }
    return {
        "status": "READY_FOR_AUTHOR_REVIEW", "draft": draft,
        "assessment": {"status": "PASS", "issues": []},
        "review": {"verdict": "PASS", "outcome": "READY", "issues": [],
                   "reviewed_draft_sha256": canonical_hash(draft),
                   "typed_review": {"outcome": "READY", "blocking_issues": [],
                                    "uncertainties": [], "advisory_notes": ["Retain advice"]},
                   "rubric_sha256": "a" * 64},
        "proposal": {"number": number, "decision": "ACCEPT", "journey_stage": stage,
                     "proposed_sutra": "Earlier fixture; revisions remain legitimate",
                     "selected_source_ids": ["fixture-ref"]},
        "discussion": {"opaque": "Original discussion"},
        "peer_review": {"fixture": {"verdict": "PASS"}},
        "review_history": [{"revision": 1, "reason": "Preserve full lineage"}],
        "revisions": 1,
    }


def test_gaps_stage_rank_and_explicit_order_preserve_every_other_value(registry):
    results = [ready(90, "people"), ready(4, "closure"), ready(21, "opening"),
               ready(7, "growth"), ready(11, "society"), ready(44, "practice")]
    before, refs_before = deepcopy(results), deepcopy(registry)
    view = exporter.prepare_presentation(results, registry)
    assert [e["id"] for e in view["entries"]] == [
        "fixture-21", "fixture-44", "fixture-90", "fixture-7", "fixture-11", "fixture-4"]
    assert [e["number"] for e in view["entries"]] == list(range(1, 7))
    assert [e["chapter"] for e in view["entries"]] == [1, 2, 3, 3, 3, 4]
    assert [c["number"] for c in view["chapters"]] == [1, 2, 3, 4]
    for entry, mapping in zip(view["entries"], view["receipt"]["numbering_map"]):
        original = results[mapping["stable_input_order"] - 1]
        restored = deepcopy(entry)
        restored.update(number=original["draft"]["number"], chapter=original["draft"]["chapter"])
        assert restored == original["draft"]
        assert canonical_hash(original["draft"]) == mapping["canonical_draft_sha256"]
        assert mapping["reviewed_draft_sha256"] == mapping["canonical_draft_sha256"]
        assert canonical_hash(entry) == mapping["presentation_draft_sha256"]
        assert mapping["presentation_draft_sha256"] != mapping["reviewed_draft_sha256"]
        assert mapping["review_binding_verified_against"] == "canonical_draft_only"
        assert mapping["presentation_copy_independently_reviewed"] is False
        assert mapping["lineage"] == {k: v for k, v in original.items() if k != "draft"}
    assert results == before and registry == refs_before
    view["entries"][0]["examples"][0]["text_mr"] = "changed only test copy"
    assert results == before


def test_same_rank_follows_supplied_list_not_logical_number(registry):
    a, b = ready(99, "society"), ready(3, "growth")
    first = exporter.prepare_presentation([a, b], registry, diagnostic_pilot=True)
    reverse = exporter.prepare_presentation([b, a], registry, diagnostic_pilot=True)
    assert [e["id"] for e in first["entries"]] == ["fixture-99", "fixture-3"]
    assert [e["id"] for e in reverse["entries"]] == ["fixture-3", "fixture-99"]


@pytest.mark.parametrize("stages", [[], ["opening"], ["closure"], ["practice", "people"]])
def test_final_boundaries_required_and_pilot_does_not_invent_them(registry, stages):
    results = [ready(n, s) for n, s in enumerate(stages, 1)]
    with pytest.raises(ValueError):
        exporter.prepare_presentation(results, registry)
    if results:
        view = exporter.prepare_presentation(results, registry, diagnostic_pilot=True)
        assert view["receipt"]["mode"] == "DIAGNOSTIC_PILOT"
        assert len(view["entries"]) == len(results)


@pytest.mark.parametrize("defect", [
    "status", "assessment", "assessment_issues", "verdict", "outcome", "hash", "missing_hash",
    "typed_outcome", "typed_issues", "typed_uncertainty", "missing_typed_outcome",
    "review_issues", "proposal_reject", "proposal_stage", "missing_proposal_stage",
    "proposal_number", "boolean_number", "missing_chapter", "result_number", "unknown_ref",
])
def test_invalid_saved_gates_are_never_relaxed_for_pilot(registry, defect):
    result = ready()
    if defect == "status": result["status"] = "NEEDS_REVIEW"
    elif defect == "assessment": result["assessment"]["status"] = "NEEDS_REVISION"
    elif defect == "assessment_issues": result["assessment"]["issues"] = ["unresolved"]
    elif defect == "verdict": result["review"]["verdict"] = "REVIEW_REQUIRED"
    elif defect == "outcome": result["review"]["outcome"] = "AUTHOR_REVIEW"
    elif defect == "hash": result["review"]["reviewed_draft_sha256"] = "0" * 64
    elif defect == "missing_hash": result["review"].pop("reviewed_draft_sha256")
    elif defect == "typed_outcome": result["review"]["typed_review"]["outcome"] = "AUTHOR_REVIEW"
    elif defect == "typed_issues": result["review"]["typed_review"]["blocking_issues"] = ["block"]
    elif defect == "typed_uncertainty": result["review"]["typed_review"]["uncertainties"] = ["open"]
    elif defect == "missing_typed_outcome": result["review"]["typed_review"].pop("outcome")
    elif defect == "review_issues": result["review"]["issues"] = ["contradiction"]
    elif defect == "proposal_reject": result["proposal"]["decision"] = "REJECT"
    elif defect == "proposal_stage": result["proposal"]["journey_stage"] = "made-up"
    elif defect == "missing_proposal_stage":
        result["proposal"].pop("journey_stage")
        result["brief"] = {"journey_stage": "opening"}  # Must not infer from planner.
    elif defect == "proposal_number": result["proposal"]["number"] += 1
    elif defect == "boolean_number": result["draft"]["number"] = True
    elif defect == "missing_chapter": result["draft"].pop("chapter")
    elif defect == "result_number": result["number"] = 999
    elif defect == "unknown_ref":
        result["draft"]["references"].append("not-registered")
        result["review"]["reviewed_draft_sha256"] = canonical_hash(result["draft"])
    with pytest.raises(ValueError):
        exporter.prepare_presentation([result], registry, diagnostic_pilot=True)


@pytest.mark.parametrize("field", ["new_sutra", "exposition", "examples", "references", "number", "chapter"])
def test_hash_is_checked_before_any_presentation_changes(registry, field):
    result = ready()
    if field in ("number", "chapter"):
        result["draft"][field] += 1
    else:
        result["draft"][field] = "changed"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        exporter.prepare_presentation([result], registry, diagnostic_pilot=True)


def test_flat_review_contract_without_optional_typed_payload_is_accepted(registry):
    result = ready()
    result["review"].pop("typed_review")
    assert exporter.prepare_presentation([result], registry, diagnostic_pilot=True)


def test_batch_proposal_lineage_and_exact_candidate_selection(registry):
    result = ready(41, "closure")
    selected = deepcopy(result["proposal"])
    result["proposal"] = {"proposals": [
        {"number": 2, "decision": "REJECT", "rejection_reason": "Unrelated candidate"},
        selected,
    ], "other_lineage": "preserve"}
    view = exporter.prepare_presentation([result], registry, diagnostic_pilot=True)
    mapping = view["receipt"]["numbering_map"][0]
    assert mapping["journey_stage"] == "closure"
    assert mapping["selected_proposal_sha256"] == canonical_hash(selected)
    assert mapping["proposal_sha256"] == canonical_hash(result["proposal"])
    assert mapping["lineage"]["proposal"] == result["proposal"]
    result["proposal"]["proposals"].append(deepcopy(selected))
    with pytest.raises(ValueError, match="Duplicate proposal"):
        exporter.prepare_presentation([result], registry, diagnostic_pilot=True)


@pytest.mark.parametrize("duplicate", ["id", "number"])
def test_duplicate_canonical_identity_rejected(registry, duplicate):
    a, b = ready(5), ready(9, "closure")
    b["draft"][duplicate] = a["draft"][duplicate]
    b["proposal"]["number"] = b["draft"]["number"]
    b["review"]["reviewed_draft_sha256"] = canonical_hash(b["draft"])
    with pytest.raises(ValueError, match="Duplicate canonical"):
        exporter.prepare_presentation([a, b], registry)


@pytest.mark.parametrize("defect", ["missing", "extra", "mismatched_id", "blank", "bad_url", "duplicate_list"])
def test_exact_explicit_registry_no_generated_fields(registry, defect):
    if defect == "missing": registry["fixture-ref"].pop("original_text")
    elif defect == "extra": registry["fixture-ref"]["meaning_en"] = "No inferred overlay"
    elif defect == "mismatched_id": registry["fixture-ref"]["id"] = "other"
    elif defect == "blank": registry["fixture-ref"]["meaning_mr"] = " "
    elif defect == "bad_url": registry["fixture-ref"]["url"] = "file:///unverified"
    elif defect == "duplicate_list": registry = list(registry.values()) * 2
    with pytest.raises(ValueError):
        exporter.prepare_presentation([ready()], registry, diagnostic_pilot=True)


def test_list_registry_records_retained_exactly(registry):
    view = exporter.prepare_presentation([ready()], list(registry.values()), diagnostic_pilot=True)
    assert view["references"] == registry


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def export_files(tmp_path, monkeypatch, registry):
    """Plain bytes and a mocked renderer only; no OOXML or protected assets."""
    opening, closing = tmp_path / "opening.fixture", tmp_path / "closing.fixture"
    opening.write_bytes(b"fake opening bytes")
    closing.write_bytes(b"fake closing bytes")
    oh, ch = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (opening, closing)]
    monkeypatch.setattr(exporter.research_book, "OPENING_SHA256", oh)
    monkeypatch.setattr(exporter.research_book, "CLOSING_SHA256", ch)
    approval = {"status": "PASS_OFFLINE_EXPORT_PREFLIGHT_ONLY", "assets": {
        "opening_v19": {"sha256": oh, "expected_sha256": oh, "hash_matches": True},
        "closing_source": {"sha256": ch, "expected_sha256": ch, "hash_matches": True},
    }}
    preflight = write_json(tmp_path / "preflight.json", approval)
    paths = [write_json(tmp_path / "result-90.json", ready(90, "closure")),
             write_json(tmp_path / "result-17.json", ready(17, "opening"))]
    refs = write_json(tmp_path / "references.json", registry)
    calls = []
    def renderer(opening_arg, closing_arg, entries, chapters, references, output):
        calls.append(deepcopy((opening_arg, closing_arg, entries, chapters, references, output)))
        with output.open("xb") as handle:
            handle.write(b"MOCK_OUTPUT_ONLY_NOT_A_DOCX_PACKAGE")
        return {"first85paragraphs_identical": True, "closing_text_identical": True,
                "render_status": "NOT_RUN", "fixture_report": True}
    monkeypatch.setattr(exporter, "render_research_book", renderer)
    return {"result_paths": paths, "references": refs, "opening": opening, "closing": closing,
            "output": tmp_path / "mock-output.docx", "preflight": preflight}, calls


def test_mock_export_receipt_source_lineage_and_inputs_untouched(export_files, registry):
    kwargs, calls = export_files
    all_inputs = kwargs["result_paths"] + [kwargs[k] for k in ("references", "opening", "closing", "preflight")]
    before = {p: p.read_bytes() for p in all_inputs}
    # A rejected neighbor is never discovered by glob or logical-number range.
    write_json(kwargs["output"].parent / "result-18.json", {"status": "REJECTED"})
    report = exporter.export(**kwargs)
    assert len(calls) == 1
    assert [e["id"] for e in calls[0][2]] == ["fixture-17", "fixture-90"]
    assert calls[0][4] == registry
    receipt = json.loads(kwargs["output"].with_suffix(".qa.json").read_text(encoding="utf-8"))
    assert receipt == report
    assert report["fresh_word_pdf_render"] == "NOT_RUN"
    assert report["fresh_protected_page_pixel_comparison"] == "NOT_RUN"
    assert report["publication_approved"] is False
    assert [m["result_file"]["path"] for m in report["numbering_map"]] == [
        str(kwargs["result_paths"][1].resolve()), str(kwargs["result_paths"][0].resolve())]
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert report["output_sha256"] == hashlib.sha256(kwargs["output"].read_bytes()).hexdigest()


@pytest.mark.parametrize("target", ["docx", "receipt"])
def test_existing_output_or_receipt_is_never_overwritten(export_files, target):
    kwargs, calls = export_files
    path = kwargs["output"] if target == "docx" else kwargs["output"].with_suffix(".qa.json")
    path.write_bytes(b"existing protected bytes")
    with pytest.raises(FileExistsError):
        exporter.export(**kwargs)
    assert path.read_bytes() == b"existing protected bytes" and not calls


@pytest.mark.parametrize("defect", ["template", "preflight_hash", "preflight_status", "held", "duplicate_path"])
def test_rejected_inputs_never_reach_renderer(export_files, defect):
    kwargs, calls = export_files
    if defect == "template":
        kwargs["opening"].write_bytes(b"changed template")
    elif defect.startswith("preflight"):
        obj = json.loads(kwargs["preflight"].read_text(encoding="utf-8"))
        if defect == "preflight_hash": obj["assets"]["opening_v19"]["sha256"] = "0" * 64
        else: obj["status"] = "NOT_APPROVED"
        write_json(kwargs["preflight"], obj)
    elif defect == "held":
        obj = ready(90, "closure")
        obj["review"]["outcome"] = "AUTHOR_REVIEW"
        write_json(kwargs["result_paths"][0], obj)
    else:
        kwargs["result_paths"].append(kwargs["result_paths"][0])
    with pytest.raises(ValueError):
        exporter.export(**kwargs)
    assert not calls and not kwargs["output"].exists()
    assert not kwargs["output"].with_suffix(".qa.json").exists()


@pytest.mark.parametrize("raw", ['{"status":"PASS","status":"FAIL"}', '{"value":NaN}'])
def test_ambiguous_json_is_rejected(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        exporter._read_json(path)


def test_renderer_mutation_does_not_receive_success_receipt(export_files, monkeypatch):
    kwargs, _ = export_files
    def mutating_renderer(opening, closing, entries, chapters, references, output):
        entries[0]["exposition"].append("forbidden content edit")
        return {}
    monkeypatch.setattr(exporter, "render_research_book", mutating_renderer)
    with pytest.raises(ValueError, match="Renderer mutated"):
        exporter.export(**kwargs)
    assert not kwargs["output"].with_suffix(".qa.json").exists()


def test_receipt_race_does_not_overwrite_other_writer(export_files, monkeypatch):
    kwargs, _ = export_files
    original = exporter.render_research_book
    def racing_renderer(*args):
        result = original(*args)
        args[-1].with_suffix(".qa.json").write_bytes(b"another writer")
        return result
    monkeypatch.setattr(exporter, "render_research_book", racing_renderer)
    with pytest.raises(FileExistsError):
        exporter.export(**kwargs)
    assert kwargs["output"].with_suffix(".qa.json").read_bytes() == b"another writer"


def test_cli_multiple_paths_and_repeat_flags_keep_explicit_order(monkeypatch, capsys):
    captured = {}
    def fake_export(paths, refs, opening, closing, output, **kwargs):
        captured.update(paths=paths, refs=refs, output=output, **kwargs)
        return {"mocked": True}
    monkeypatch.setattr(exporter, "export", fake_export)
    assert exporter.main(["--result", "z.json", "a.json", "--result", "b.json",
                          "--references", "refs.json", "--opening", "open.docx",
                          "--closing", "close.docx", "--output", "new.docx",
                          "--diagnostic-pilot"]) == 0
    assert captured["paths"] == list(map(Path, ["z.json", "a.json", "b.json"]))
    assert captured["diagnostic_pilot"] is True
    assert json.loads(capsys.readouterr().out) == {"mocked": True}


def test_import_performs_no_file_io(monkeypatch):
    spec = importlib.util.spec_from_file_location("source_first_export_inert", exporter.__file__)
    module = importlib.util.module_from_spec(spec)
    def forbidden(*args, **kwargs):
        raise AssertionError("Import attempted input/output")
    with monkeypatch.context() as context:
        context.setattr(Path, "read_bytes", forbidden)
        context.setattr(Path, "open", forbidden)
        spec.loader.exec_module(module)
    assert callable(module.prepare_presentation)



def test_optional_display_labels_preserve_canonical_evidence_and_review_hashes(registry):
    """Display-only fields live in separate copies; canonical eight-field refs stay exact."""
    result=ready();before=deepcopy((result,registry))
    overlay={'fixture-ref':{'title_mr':'चाचणी ग्रंथ','author_mr':'चाचणी लेखक',
                            'locator_mr':'प्रकरण २','tradition_mr':'चाचणी परंपरा'}}
    default=exporter.prepare_presentation([result],registry,diagnostic_pilot=True)
    view=exporter.prepare_presentation([result],registry,diagnostic_pilot=True,
                                       reference_display_overlay=overlay)
    assert (result,registry)==before
    assert view['references']==registry
    assert set(view['references']['fixture-ref'])==set(exporter.REFERENCE_FIELDS)
    assert 'display_references' not in default and 'reference_display' not in default['receipt']
    assert exporter.prepare_presentation([result],registry,diagnostic_pilot=True,
                                          reference_display_overlay=None)==default
    assert view['entries']==default['entries']
    assert view['receipt']['numbering_map']==default['receipt']['numbering_map']
    for key in ('canonical_references_sha256','canonical_reference_record_hashes'):
        assert view['receipt'][key]==default['receipt'][key]
    for field,value in overlay['fixture-ref'].items():
        assert view['display_references']['fixture-ref'][field]==value
    assert view['display_references']['fixture-ref']['original_text']==registry['fixture-ref']['original_text']
    assert view['display_references']['fixture-ref']['url']==registry['fixture-ref']['url']
    audit=view['receipt']['reference_display']
    assert audit['overlay_canonical_sha256']==canonical_hash(overlay)
    assert {x['field'] for x in audit['field_changes']}==set(overlay['fixture-ref'])
    assert audit['canonical_reference_records_changed'] is False
    assert audit['canonical_drafts_and_review_hashes_changed'] is False


@pytest.mark.parametrize('field',['id','url','original_text','meaning_mr','author','title','locator','tradition','unknown_mr'])
def test_display_overlay_cannot_modify_any_canonical_or_unknown_field(registry,field):
    """Only the four declared presentation labels are admissible, never source content."""
    with pytest.raises(ValueError,match='only'):
        exporter.prepare_presentation([ready()],registry,diagnostic_pilot=True,
            reference_display_overlay={'fixture-ref':{field:'बदल नको'}})


@pytest.mark.parametrize('overlay',[[], 'bad', {'unknown':{'title_mr':'ग्रंथ'}},
    {'fixture-ref':{}},{'fixture-ref':{'title_mr':None}},{'fixture-ref':{'author_mr':False}},
    {'fixture-ref':{'locator_mr':'  '}},{'fixture-ref':{'tradition_mr':4}}])
def test_display_overlay_rejects_unknown_ids_and_malformed_labels(registry,overlay):
    """Reject unsafe display data without a renderer call or inferred normalization."""
    before=deepcopy(registry)
    with pytest.raises(ValueError):
        exporter.prepare_presentation([ready()],registry,diagnostic_pilot=True,
                                       reference_display_overlay=overlay)
    assert registry==before


def test_export_binds_overlay_bytes_and_field_changes_without_source_mutation(export_files,registry):
    """The optional file is snapshotted and audited while rendered copies alone differ."""
    kwargs,calls=export_files
    overlay={'fixture-ref':{'author_mr':'चाचणी लेखक','title_mr':'चाचणी ग्रंथ'}}
    path=write_json(kwargs['output'].parent/'labels.json',overlay)
    before={p:p.read_bytes() for p in kwargs['result_paths']+[kwargs['references'],path]}
    report=exporter.export(**kwargs,reference_display=path)
    shown=calls[0][4]['fixture-ref']
    assert shown['author_mr']=='चाचणी लेखक' and shown['title_mr']=='चाचणी ग्रंथ'
    assert all(shown[k]==v for k,v in registry['fixture-ref'].items())
    assert report['reference_display_file']=={'path':str(path.resolve()),
        'sha256':hashlib.sha256(before[path]).hexdigest()}
    assert report['reference_display']['overlay_canonical_sha256']==canonical_hash(overlay)
    assert len(report['reference_display']['field_changes'])==2
    assert report['canonical_reference_record_hashes']['fixture-ref']==canonical_hash(registry['fixture-ref'])
    assert all(p.read_bytes()==raw for p,raw in before.items())


def test_overlay_input_change_during_render_gets_no_success_receipt(export_files,monkeypatch):
    """Overlay integrity is checked after rendering just like canonical input integrity."""
    kwargs,_=export_files
    path=write_json(kwargs['output'].parent/'labels.json',{'fixture-ref':{'title_mr':'ग्रंथ'}})
    render=exporter.render_research_book
    def mutate_overlay(*args):
        """Simulate concurrent label-file mutation after the input snapshot."""
        result=render(*args);path.write_bytes(path.read_bytes()+b' ');return result
    monkeypatch.setattr(exporter,'render_research_book',mutate_overlay)
    with pytest.raises(ValueError,match='Input changed'):
        exporter.export(**kwargs,reference_display=path)
    assert not kwargs['output'].with_suffix('.qa.json').exists()


def test_overlay_duplicate_json_keys_fail_before_renderer(export_files):
    """Ambiguous display records cannot silently replace a supplied label."""
    kwargs,calls=export_files;path=kwargs['output'].parent/'labels.json'
    path.write_text('{"fixture-ref":{"title_mr":"अ","title_mr":"ब"}}',encoding='utf-8')
    with pytest.raises(ValueError,match='Duplicate JSON key'):
        exporter.export(**kwargs,reference_display=path)
    assert not calls and not kwargs['output'].exists()


def test_cli_reference_display_is_explicit_optional_path(monkeypatch):
    """Forward the requested label file without discovering or changing canonical refs."""
    captured={}
    def fake_export(*args,**kwargs):
        """Capture CLI adapter arguments, no package or source writes."""
        captured.update(kwargs);return {'mocked':True}
    monkeypatch.setattr(exporter,'export',fake_export)
    assert exporter.main(['--result','r.json','--references','refs.json','--reference-display','labels.json',
        '--opening','o.docx','--closing','c.docx','--output','new.docx','--diagnostic-pilot'])==0
    assert captured['reference_display']==Path('labels.json')
