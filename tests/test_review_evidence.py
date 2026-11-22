"""Offline evidence-selector contracts; synthetic passages and fake callbacks only.

Purpose: reject ungrounded references without changing model verdicts or raw audit.
Parameters: pytest fixtures/local temporary caches. Returns: assertions only.
Failures: expose selector/cache regressions; never call providers or edit live data.
"""

import json
import sqlite3
from copy import deepcopy
from unittest.mock import Mock

import pytest

from src.orchestration import independent_review as review
from src.orchestration.review_evidence import evidence_catalog, evidence_selection, materialize_review


@pytest.fixture
def inputs():
    """Purpose: supply two independent sources/cases/comparisons. Parameters: none.
    Returns: synthetic draft, packet and cards. Failures: none; no external evidence.
    """
    sources = {
        "references": [
            {"id": "S1", "original_text": "Ask questions before deciding.", "meaning_mr": "निर्णयापूर्वी प्रश्न विचारा."},
            {"id": "S2", "original_text": "Keep a record of decisions.", "meaning_mr": "निर्णयाची नोंद ठेवा."},
        ],
        "examples": [
            {"case_id": "C1", "text_mr": "The company ran a pilot."},
            {"case_id": "C2", "text_mr": "The company ran a pilot."},
        ],
    }
    draft = {
        "id": "entry-1", "number": 1, "chapter": 1, "title_mr": "विचारपूर्वक निर्णय",
        "new_sutra": "उद्यमेन विवेकः", "grammar_mr": "Synthetic grammar explanation.",
        "translation_mr": "विचारपूर्वक निर्णय घ्या.", "exposition": ["विचार " * 500],
        "references": deepcopy(sources["references"]), "examples": deepcopy(sources["examples"]),
        "comparative_mr": [
            {"source_id": "S1", "explanation_mr": "Ask questions before deciding. Modern business analogy: ask customers before testing."},
            {"source_id": "S2", "explanation_mr": "Keep a record of decisions. Modern business analogy: record approval reasons."},
        ],
        "dos_mr": ["प्रश्न विचारा."], "donts_mr": ["घाई टाळा."],
        "application_mr": "निर्णयापूर्वी पर्याय तपासा.", "action_mr": "विरोधी मत नोंदवा.",
        "summary_mr": "विचारपूर्वक निर्णय घ्या.",
    }
    return draft, sources, []


def selected_payload(inputs):
    """Purpose: construct the authoritative test catalog. Parameters: review inputs.
    Returns: detached payload with selection map. Failures: malformed evidence raises.
    """
    payload = review.build_payload(*inputs)
    payload["evidence_selection"] = evidence_selection(payload)
    return payload


def find_ref(payload, kind, field, owner=None, scope="whole", text=None):
    """Purpose: select an unambiguous synthetic reference. Parameters: row identity.
    Returns: catalog ID. Failures: absent/ambiguous fixture row fails an assertion.
    """
    matches = [key for key, row in payload["evidence_selection"]["catalog"].items()
               if row["kind"] == kind and row["field"] == field and row["owner_id"] == owner
               and row["scope"] == scope and (text is None or row["text"] == text)]
    assert len(matches) == 1, matches
    return matches[0]


def wire_response(payload):
    """Purpose: build a valid reference-only analogy review. Parameters: payload.
    Returns: six-root-field model response. Failures: incomplete fixture evidence.
    """
    checks = []
    catalog = payload["evidence_selection"]["catalog"]
    for menu in payload["evidence_selection"]["comparisons"]:
        sentences = [key for key in menu["draft_refs"] if catalog[key]["scope"] == "sentence"]
        assert len(sentences) == 2
        source = next(key for key in menu["source_refs"] if catalog[key]["field"] == "original_text")
        checks.append({"comparison_ref": menu["comparison_ref"], "source_claim_ref": sentences[0],
                       "application_ref": sentences[1], "source_ref": source,
                       "classification": "QUALIFIED_ANALOGY", "reason": "Explicit modern analogy follows the source statement."})
    decisions = {card["id"]: ("EXACT_COPY" if card["same_formula"] else
                 "SAME_DECISION" if card["identical_decision_and_action"] else "DISTINCT")
                 for card in payload["decision_comparisons"]["prior"]}
    return {"decision_checks": decisions, "source_checks": checks, "outcome": "READY", "blocking_issues": [],
            "advisory_notes": [], "uncertainties": []}


def negative_source_response(inputs):
    """Purpose: retain false attribution despite a modern-analogy disclaimer.
    Parameters: clean synthetic inputs. Returns: modified inputs, payload and raw
    negative response. Failures: absent required fixture references fail assertions.
    """
    supplied = deepcopy(inputs)
    supplied[0]["comparative_mr"][0]["explanation_mr"] = (
        "The passage orders every business to launch within 24 hours. "
        "This is our modern business analogy, not an ancient operational rule.")
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw["source_checks"][0]["classification"] = "FALSE_ATTRIBUTION"
    check = raw["source_checks"][0]
    raw["outcome"] = "REVISION_REQUIRED"
    raw["blocking_issues"] = [{"category": "SOURCE_DISTORTION", "draft_ref": check["source_claim_ref"],
        "reason": "The canonical passage does not prescribe a 24-hour product launch.",
        "evidence": {"source_ref": check["source_ref"]}}]
    return supplied, payload, raw


def cached_rows(path):
    """Purpose: inspect only a temporary audit. Parameters: SQLite path.
    Returns: state/raw/error records. Failures: SQL errors expose broken persistence.
    """
    with sqlite3.connect(path) as db:
        return db.execute("SELECT state,response_json,error FROM independent_reviews_v2 ORDER BY rowid").fetchall()


def test_catalog_is_deterministic_and_ownership_bound(inputs):
    """Purpose: bind typed owner/field/scope/text, even when texts coincide.
    Parameters: fixture. Returns: None. Failures: unstable IDs or identity collapse.
    """
    payload = selected_payload(inputs)
    assert evidence_catalog(payload) == evidence_catalog(deepcopy(payload))
    assert evidence_selection(payload) == payload["evidence_selection"]
    c1 = find_ref(payload, "case", "text_mr", "C1")
    c2 = find_ref(payload, "case", "text_mr", "C2")
    d1 = find_ref(payload, "draft", "examples.0.text_mr", "C1")
    assert len({c1, c2, d1}) == 3
    catalog = payload["evidence_selection"]["catalog"]
    assert catalog[c1]["text"] == catalog[c2]["text"] == catalog[d1]["text"]
    first = payload["evidence_selection"]["comparisons"][0]
    assert catalog[first["comparison_ref"]]["scope"] == "whole"
    assert all(catalog[key]["owner_id"] == "S1" for key in first["source_refs"])


def test_valid_wire_materializes_only_canonical_text_and_preserves_inputs(inputs):
    """Purpose: derive literal quotes/paths without paraphrasing or mutating raw.
    Parameters: fixture. Returns: None. Failures: altered text, lost choices or aliases.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    saved_raw, saved_payload = deepcopy(raw), deepcopy(payload)
    canonical, audit = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["outcome"] == "READY"
    check = canonical["source_checks"][0]
    assert check["field"] == "comparative_mr.0.explanation_mr" and check["source_id"] == "S1"
    assert check["source_claim_quote"] == inputs[1]["references"][0]["original_text"]
    assert check["application_quote"] == "Modern business analogy: ask customers before testing."
    assert check["source_quote"] == inputs[1]["references"][0]["original_text"]
    assert all(set(row) == {"response_path", "ref"} for row in audit)
    assert all(row["ref"] in payload["evidence_selection"]["catalog"] for row in audit)
    canonical["source_checks"][0]["reason"] = "caller mutation"
    assert raw == saved_raw and payload == saved_payload


@pytest.mark.parametrize("field", ["comparison_ref", "source_claim_ref", "application_ref", "source_ref"])
def test_invented_source_check_reference_is_rejected(inputs, field):
    """Purpose: reject fabricated IDs without guessing. Parameters: reference position.
    Returns: None. Failures: invented reference falls back to text or another field.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0][field] = "D000000000000"
    with pytest.raises(ValueError):
        materialize_review(raw, payload)


@pytest.mark.parametrize("field,kind", [("source_ref", "draft"), ("source_claim_ref", "source"),
                                       ("application_ref", "case")])
def test_source_checks_reject_cross_type_references(inputs, field, kind):
    """Purpose: enforce typed catalog references. Parameters: target and wrong kind.
    Returns: None. Failures: a real ID with an invalid evidence type resolves.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0][field] = next(k for k, v in payload["evidence_selection"]["catalog"].items() if v["kind"] == kind)
    with pytest.raises(ValueError, match="wrong-kind"):
        materialize_review(raw, payload)


@pytest.mark.parametrize("field", ["source_claim_ref", "application_ref"])
def test_claim_and_application_cannot_select_another_current_field(inputs, field):
    """Purpose: require selectors from this comparison. Parameters: reference position.
    Returns: None. Failures: another valid draft field is borrowed as its evidence.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0][field] = raw["source_checks"][1][field]
    with pytest.raises(ValueError, match="another draft field"):
        materialize_review(raw, payload)


def test_source_check_cannot_select_another_source(inputs):
    """Purpose: bind each comparison's canonical owner. Parameters: fixture.
    Returns: None. Failures: a valid different source supports this comparison.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0]["source_ref"] = raw["source_checks"][1]["source_ref"]
    with pytest.raises(ValueError, match="another comparison's source"):
        materialize_review(raw, payload)


def test_comparison_ref_must_identify_whole_comparison(inputs):
    """Purpose: prohibit narrowing mandatory full-comparison coverage. Parameters: fixture.
    Returns: None. Failures: a sentence is accepted as the whole comparison selector.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0]["comparison_ref"] = raw["source_checks"][0]["source_claim_ref"]
    with pytest.raises(ValueError, match="whole current comparison"):
        materialize_review(raw, payload)


@pytest.mark.parametrize("changed", ["draft", "source", "case"])
def test_changed_evidence_invalidates_old_references(inputs, changed):
    """Purpose: reject content-stale selectors against a freshly computed index.
    Parameters: changed evidence kind. Returns: None. Failures: old ID survives changed text.
    """
    supplied = deepcopy(inputs)
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    if changed == "draft":
        supplied[0]["comparative_mr"][0]["explanation_mr"] += " Changed text."
    elif changed == "source":
        supplied[1]["references"][0]["original_text"] += " Changed text."
    else:
        raw["outcome"] = "REVISION_REQUIRED"
        raw["blocking_issues"] = [{"category": "CASE_FACT", "draft_ref": find_ref(payload, "draft", "examples.0.text_mr", "C1"),
            "reason": "Synthetic case discrepancy.", "evidence": {"case_ref": find_ref(payload, "case", "text_mr", "C1")}}]
        supplied[1]["examples"][0]["text_mr"] += " Changed canonical facts."
    fresh = selected_payload(supplied)
    with pytest.raises(ValueError):
        materialize_review(raw, fresh)


@pytest.mark.parametrize("tamper", ["text", "kind", "owner_id", "field", "scope", "menu", "remove", "missing_index"])
def test_decoder_recomputes_and_rejects_tampered_external_index(inputs, tamper):
    """Purpose: distrust externally supplied catalog/menu data. Parameters: tampering.
    Returns: None. Failures: altered content, identity or menus influence materialization.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    key = raw["source_checks"][0]["source_ref"]
    if tamper == "missing_index":
        payload.pop("evidence_selection")
    elif tamper == "menu":
        payload["evidence_selection"]["comparisons"][0]["source_refs"].append(raw["source_checks"][1]["source_ref"])
    elif tamper == "remove":
        del payload["evidence_selection"]["catalog"][key]
    else:
        payload["evidence_selection"]["catalog"][key][tamper] = "tampered"
    with pytest.raises(ValueError, match="catalog differs"):
        materialize_review(raw, payload)


def test_selection_rejects_missing_canonical_comparison_source(inputs):
    """Purpose: fail before inference when canonical source evidence is absent.
    Parameters: fixture. Returns: None. Failures: unresolved source receives a menu.
    """
    payload = review.build_payload(*inputs)
    payload["canonical_sources"]["references"] = []
    with pytest.raises(ValueError, match="canonical source evidence"):
        evidence_selection(payload)


@pytest.mark.parametrize("injected", ["quote", "field", "source_quote", "replacement_draft"])
def test_wire_rejects_generated_literal_or_edit_fields(inputs, injected):
    """Purpose: forbid fallback to generated quotes or edits. Parameters: extra field.
    Returns: None. Failures: undeclared text bypasses canonical selector lookup.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0][injected] = "fabricated"
    with pytest.raises(ValueError, match="missing or unexpected fields"):
        materialize_review(raw, payload)


def test_legacy_literal_response_is_not_recovered_as_reference_wire(inputs):
    """Purpose: refuse old invalid-quote recovery through the new protocol.
    Parameters: fixture. Returns: None. Failures: obsolete literal checks are guessed.
    """
    payload = selected_payload(inputs)
    canonical, _ = materialize_review(wire_response(payload), payload)
    with pytest.raises(ValueError, match="exactly six root fields"):
        materialize_review(canonical, payload)


def test_false_claim_with_disclaimer_stays_revision_required(inputs):
    """Purpose: preserve a grounded negative with canonical source/claim selectors.
    Parameters: fixture. Returns: None. Failures: materialization clears a mixed false claim.
    """
    _, payload, raw = negative_source_response(inputs)
    canonical, _ = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["outcome"] == "REVISION_REQUIRED"
    blocker, check = canonical["blocking_issues"][0], canonical["source_checks"][0]
    assert blocker["field"] == check["field"]
    assert blocker["quote"] == check["source_claim_quote"]
    assert blocker["evidence"] == {"source_id": "S1", "source_quote": "Ask questions before deciding."}
    assert check["application_quote"] == "This is our modern business analogy, not an ancient operational rule."


def test_materialization_does_not_supply_missing_blocker_or_force_pass(inputs):
    """Purpose: keep disposition and completeness under existing validation.
    Parameters: fixture. Returns: None. Failures: decoder invents blockers or accepts a false READY.
    """
    _, payload, raw = negative_source_response(inputs)
    raw["blocking_issues"] = []
    raw["outcome"] = "READY"
    canonical, _ = materialize_review(raw, payload)
    assert canonical["outcome"] == "READY" and canonical["blocking_issues"] == []
    with pytest.raises(ValueError, match="matching source blocker"):
        review.validate_review(canonical, payload)


def test_source_blocker_rejects_cross_source_and_wrong_type_refs(inputs):
    """Purpose: bind blocker source selectors too. Parameters: fixture.
    Returns: None. Failures: valid foreign or case references support a source blocker.
    """
    _, payload, raw = negative_source_response(inputs)
    for bad in (raw["source_checks"][1]["source_ref"], find_ref(payload, "case", "text_mr", "C1")):
        changed = deepcopy(raw)
        changed["blocking_issues"][0]["evidence"]["source_ref"] = bad
        with pytest.raises(ValueError):
            materialize_review(changed, payload)


def test_case_negative_materializes_exact_current_and_canonical_facts(inputs):
    """Purpose: keep a substantive case-fact hold. Parameters: fixture.
    Returns: None. Failures: canonical facts are replaced or a negative becomes READY.
    """
    supplied = deepcopy(inputs)
    supplied[0]["examples"][0]["text_mr"] += " Every customer doubled income."
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", blocking_issues=[{
        "category": "CASE_FACT", "draft_ref": find_ref(payload, "draft", "examples.0.text_mr", "C1"),
        "reason": "The canonical facts contain no universal income outcome.",
        "evidence": {"case_ref": find_ref(payload, "case", "text_mr", "C1")}}])
    canonical, _ = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["blocking_issues"][0]["quote"] == supplied[0]["examples"][0]["text_mr"]
    assert canonical["blocking_issues"][0]["evidence"] == {"case_id": "C1", "canonical_quote": "The company ran a pilot."}
    for bad in (find_ref(payload, "case", "text_mr", "C2"), raw["source_checks"][0]["source_ref"]):
        changed = deepcopy(raw)
        changed["blocking_issues"][0]["evidence"]["case_ref"] = bad
        with pytest.raises(ValueError):
            materialize_review(changed, payload)


@pytest.mark.parametrize("bad", ["invented", "source", "case"])
def test_blocker_and_uncertainty_require_real_draft_refs(inputs, bad):
    """Purpose: enforce draft selectors for objections and questions.
    Parameters: invalid kind. Returns: None. Failures: wrong-kind or invented draft ID resolves.
    """
    payload = selected_payload(inputs)
    ref = ("D000000000000" if bad == "invented" else
           next(k for k, v in payload["evidence_selection"]["catalog"].items() if v["kind"] == bad))
    for uncertain in (False, True):
        raw = wire_response(payload)
        if uncertain:
            raw.update(outcome="AUTHOR_REVIEW", uncertainties=[{"category": "LEXICAL_AMBIGUITY", "draft_ref": ref,
                                                                "question": "Which lexical sense is intended?"}])
        else:
            raw.update(outcome="REVISION_REQUIRED", blocking_issues=[{"category": "GRAMMAR", "draft_ref": ref,
                "reason": "Synthetic grammar defect.", "evidence": {"rule": "agreement", "explanation": "Synthetic explanation."}}])
        with pytest.raises(ValueError, match="wrong-kind"):
            materialize_review(raw, payload)


def test_lexical_uncertainty_remains_author_review(inputs):
    """Purpose: preserve questions and human holds. Parameters: fixture.
    Returns: None. Failures: selector decoding suppresses uncertainty or changes outcome.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw.update(outcome="AUTHOR_REVIEW", uncertainties=[{"category": "LEXICAL_AMBIGUITY",
        "draft_ref": find_ref(payload, "draft", "new_sutra"), "question": "Which sense of विवेकः is intended?"}])
    canonical, _ = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["outcome"] == "AUTHOR_REVIEW"
    assert canonical["uncertainties"][0]["field"] == "new_sutra"
    assert canonical["uncertainties"][0]["quote"] == inputs[0]["new_sutra"]


def test_exact_copy_selects_formula_without_alias_guessing(inputs):
    """Purpose: retain literal-copy checks with exact draft selectors. Parameters: fixture.
    Returns: None. Failures: selectors bypass objective duplicate validation.
    """
    supplied = deepcopy(inputs)
    supplied[2].append({"id": "prior", "formula": supplied[0]["new_sutra"], "decision_mr": "Same decision", "action_mr": "Same action"})
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", blocking_issues=[{"category": "EXACT_COPY",
        "draft_ref": find_ref(payload, "draft", "new_sutra"), "reason": "Exact prior formula.", "evidence": {"comparator_id": "prior"}}])
    canonical, _ = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["blocking_issues"][0]["field"] == "new_sutra"
    raw["blocking_issues"][0]["evidence"]["comparator_id"] = "invented"
    with pytest.raises(ValueError):
        canonical, _ = materialize_review(raw, payload)
        review.validate_review(canonical, payload)


def test_reference_cache_retains_raw_response_and_replays_detached_copy(tmp_path, inputs):
    """Purpose: exercise integrated decoding with zero-call replay and raw retention.
    Parameters: temporary DB/fixture. Returns: None. Failures: paid replay, raw overwrite,
    mutable cache leakage or canonical rejection becoming PASS.
    """
    supplied, payload, raw = negative_source_response(inputs)
    original = deepcopy(raw)
    callback = Mock(return_value=raw)
    path = tmp_path / "selectors.sqlite3"
    first = review.IndependentReviewer(path, callback).review(*supplied)
    assert first["verdict"] == "REVIEW_REQUIRED" and first["outcome"] == "REVISION_REQUIRED"
    assert first["typed_review"] == materialize_review(original, payload)[0]
    assert first["evidence_selections"] == materialize_review(original, payload)[1]
    persisted = cached_rows(path)
    assert len(persisted) == 1 and persisted[0][0] == "COMPLETE"
    assert json.loads(persisted[0][1]) == original
    assert raw == original
    first["typed_review"]["source_checks"][0]["reason"] = "caller changed decoded copy"
    raw["source_checks"][0]["reason"] = "caller changed provider object"
    no_call = Mock(side_effect=AssertionError("Cached selectors must not dispatch"))
    replay = review.IndependentReviewer(path, no_call).review(*supplied)
    assert replay["typed_review"] == materialize_review(original, payload)[0]
    assert replay["evidence_selections"] == materialize_review(original, payload)[1]
    callback.assert_called_once()
    no_call.assert_not_called()


def test_invalid_reference_cache_stays_failed_without_auto_recovery(tmp_path, inputs):
    """Purpose: persist invented selectors and prohibit automatic quote recovery.
    Parameters: temporary DB/fixture. Returns: None. Failures: invalid response is
    silently repaired, retried, discarded or converted to an accepted review.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0]["source_ref"] = "S000000000000"
    callback = Mock(return_value=raw)
    path = tmp_path / "selectors.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*inputs)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*inputs)
    persisted = cached_rows(path)
    assert len(persisted) == 1 and persisted[0][0] == "FAILED"
    assert json.loads(persisted[0][1]) == raw
    callback.assert_called_once()



@pytest.mark.parametrize("nullable", ["source_claim_ref", "application_ref"])
def test_nullable_selectors_materialize_empty_quote_without_invention(inputs, nullable):
    """Purpose: allow explicitly absent claim/application selections only as null.
    Parameters: nullable position. Returns: None. Failures: fabricated text replaces
    null, a source lookup disappears, or empty-string references are guessed.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    raw["source_checks"][0][nullable] = None
    if nullable == "application_ref":
        raw["source_checks"][0]["classification"] = "SUPPORTED_ORIGINAL"
    canonical, audit = materialize_review(raw, payload)
    quote_key = "source_claim_quote" if nullable == "source_claim_ref" else "application_quote"
    assert canonical["source_checks"][0][quote_key] == ""
    assert canonical["source_checks"][0]["source_quote"] == inputs[1]["references"][0]["original_text"]
    assert not any(item["response_path"] == "source_checks.0." + nullable for item in audit)
    assert review.validate_review(canonical, payload) == canonical
    raw["source_checks"][0][nullable] = ""
    with pytest.raises(ValueError, match="wrong-kind"):
        materialize_review(raw, payload)



@pytest.mark.parametrize("category,rule,wrong_field", [
    ("EXACT_COPY", None, "grammar_mr"),
    ("EXACT_COPY", None, "application_mr"),
    ("MECHANICAL", "word_limit", "grammar_mr"),
    ("MECHANICAL", "word_limit", "application_mr"),
    ("MECHANICAL", "character_limit", "grammar_mr"),
    ("MECHANICAL", "character_limit", "application_mr"),
    ("MECHANICAL", "exposition_minimum", "grammar_mr"),
    ("MECHANICAL", "exposition_minimum", "new_sutra"),
])
def test_objective_blocker_rejects_real_reference_to_wrong_field(inputs, category, rule, wrong_field):
    """Purpose: bind objective findings to formula or exposition evidence fields.
    Parameters: objective category/rule and wrong field. Returns: None. Failures:
    a genuine draft reference with a misleading field bypasses objective anchoring.
    """
    supplied = deepcopy(inputs)
    if category == "EXACT_COPY":
        supplied[2].append({"id": "prior", "formula": supplied[0]["new_sutra"],
                            "decision_mr": "Same decision", "action_mr": "Same action"})
        proof = {"comparator_id": "prior"}
    else:
        proof = {"rule": rule}
        if rule == "word_limit":
            supplied[0]["new_sutra"] = "एकं द्वे त्रीणि चत्वारि पञ्च"
        elif rule == "character_limit":
            supplied[0]["new_sutra"] = "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं कुर्यात्"
        else:
            supplied[0]["exposition"] = ["विचार " * 499]
    correct_field = "exposition.0" if rule == "exposition_minimum" else "new_sutra"
    if wrong_field != "new_sutra":
        # Identical text in another field still cannot prove the objective finding.
        supplied[0][wrong_field] = (supplied[0]["exposition"][0] if rule == "exposition_minimum"
                                     else supplied[0]["new_sutra"])
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", blocking_issues=[{
        "category": category, "draft_ref": find_ref(payload, "draft", wrong_field),
        "reason": "Synthetic actual objective violation.", "evidence": proof,
    }])
    original = deepcopy(raw)
    expected_error = ("exposition paragraph" if rule == "exposition_minimum" else "current formula")
    with pytest.raises(ValueError, match=expected_error):
        materialize_review(raw, payload)
    assert raw == original
    # The same actual defect succeeds when grounded in its required draft field.
    raw["blocking_issues"][0]["draft_ref"] = find_ref(payload, "draft", correct_field)
    canonical, _ = materialize_review(raw, payload)
    assert canonical["blocking_issues"][0]["field"] == correct_field
    assert review.validate_review(canonical, payload) == canonical



def alternate_case_response(inputs):
    """Purpose: build the observed owner-plus-canonical selector shape.
    Parameters: synthetic inputs. Returns: inputs, payload, raw negative response.
    Failures: fixture IDs must resolve; no evidence is inferred from owner alone.
    """
    supplied = deepcopy(inputs)
    supplied[0]["examples"][0]["text_mr"] += " Every customer doubled income."
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", blocking_issues=[{
        "category": "CASE_FACT", "draft_ref": find_ref(payload, "draft", "examples.0.text_mr", "C1"),
        "reason": "The canonical case does not claim universal income growth.",
        "evidence": {"case_ref": "C1", "canonical_ref": find_ref(payload, "case", "text_mr", "C1")}}])
    return supplied, payload, raw


def seed_failed_case_shape(path, supplied, raw, *, state="FAILED",
                           error="ValueError: Reference record has missing or unexpected fields"):
    """Purpose: seed only a temporary pre-fix failed record. Parameters: row inputs.
    Returns: exact request key. Failures: SQL/JSON errors; no callback is invoked.
    """
    review.IndependentReviewer(path, Mock(side_effect=AssertionError("Seed cannot dispatch")))
    payload = review.build_payload(*supplied)
    prompt = review.CONTRACT + "\nEVIDENCE\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    request = {"contract_hash": review.contract_hash(), "payload": payload, "prompt": prompt, "system": review.SYSTEM}
    key = review.canonical_hash(request)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO independent_reviews_v2 VALUES (?,?,?,?,?)",
                   (key, state, json.dumps(request, ensure_ascii=False), json.dumps(raw, ensure_ascii=False), error))
    return key


def retained_review_row(path, key):
    """Purpose: snapshot exact retained audit strings. Parameters: temporary DB/key.
    Returns: state/request/raw/error tuple. Failures: SQL errors propagate.
    """
    with sqlite3.connect(path) as db:
        return db.execute("SELECT state,request_json,response_json,error FROM independent_reviews_v2 WHERE review_key=?", (key,)).fetchone()


def test_alternate_case_shape_preserves_negative_and_explicit_selection(inputs):
    """Purpose: accept only agreeing owner and canonical selectors.
    Parameters: fixture. Returns: None. Failures: inferred quote, lost negative or raw edit.
    """
    _, payload, raw = alternate_case_response(inputs)
    original = deepcopy(raw)
    canonical, audit = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["outcome"] == "REVISION_REQUIRED"
    assert canonical["blocking_issues"][0]["evidence"] == {"case_id": "C1", "canonical_quote": "The company ran a pilot."}
    assert {"response_path": "blocking_issues.0.evidence.canonical_ref",
            "ref": raw["blocking_issues"][0]["evidence"]["canonical_ref"]} in audit
    assert raw == original
    standard = deepcopy(raw)
    standard["blocking_issues"][0]["evidence"] = {"case_ref": raw["blocking_issues"][0]["evidence"]["canonical_ref"]}
    assert materialize_review(standard, payload)[0] == canonical


@pytest.mark.parametrize("mismatch", ["owner", "target_case", "source_kind", "draft_kind", "invented",
                                      "extra", "missing_owner", "null_canonical"])
def test_alternate_case_shape_rejects_unproven_or_extra_references(inputs, mismatch):
    """Purpose: reject owner/type/target/shape mismatches without inferring an ID.
    Parameters: mismatch. Returns: None. Failures: a business owner substitutes for
    canonical selection, or another case passes because its text happens to match.
    """
    _, payload, raw = alternate_case_response(inputs)
    proof = raw["blocking_issues"][0]["evidence"]
    if mismatch == "owner":
        proof["case_ref"] = "C2"
    elif mismatch == "target_case":
        proof.update(case_ref="C2", canonical_ref=find_ref(payload, "case", "text_mr", "C2"))
    elif mismatch == "source_kind":
        proof["canonical_ref"] = raw["source_checks"][0]["source_ref"]
    elif mismatch == "draft_kind":
        proof["canonical_ref"] = raw["blocking_issues"][0]["draft_ref"]
    elif mismatch == "invented":
        proof["canonical_ref"] = "C000000000000"
    elif mismatch == "extra":
        proof["canonical_quote"] = "The company ran a pilot."
    elif mismatch == "missing_owner":
        del proof["case_ref"]
    else:
        proof["canonical_ref"] = None
    with pytest.raises(ValueError):
        materialize_review(raw, payload)


def test_alternate_case_shape_rejects_stale_canonical_reference(inputs):
    """Purpose: invalidate a canonical selector after case evidence changes.
    Parameters: fixture. Returns: None. Failures: unchanged business ID revives stale text.
    """
    supplied, _, raw = alternate_case_response(inputs)
    supplied[1]["examples"][0]["text_mr"] += " Updated canonical facts."
    with pytest.raises(ValueError, match="wrong-kind"):
        materialize_review(raw, selected_payload(supplied))


def test_case_shape_recovery_keeps_failed_raw_and_replays_negative_without_calls(tmp_path, inputs):
    """Purpose: recover one diagnosed schema failure without rewriting its history.
    Parameters: local cache/fixture. Returns: None. Failures: changed FAILED/raw row,
    non-idempotent records, callback calls or promotion to PASS.
    """
    supplied, payload, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    before = retained_review_row(path, key)
    callback = Mock(side_effect=AssertionError("Explicit recovery/replay cannot dispatch"))
    reviewer = review.IndependentReviewer(path, callback)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        reviewer.review(*supplied)
    record = review.recover_case_reference_shape(path, key)
    assert record["provider_calls"] == 0 and record["review_key"] == key
    assert record["raw_response_sha256"] == review.canonical_hash(raw)
    canonical, audit = materialize_review(raw, payload)
    assert record["canonical_sha256"] == review.canonical_hash(canonical)
    assert record["selections"] == audit
    assert retained_review_row(path, key) == before
    assert review.recover_case_reference_shape(path, key) == record
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_reference_recoveries").fetchone()[0] == 1
    result = reviewer.review(*supplied)
    assert result["reference_recovery"] == record and result["evidence_selections"] == audit
    assert result["typed_review"] == canonical
    assert result["outcome"] == "REVISION_REQUIRED" and result["verdict"] == "REVIEW_REQUIRED"
    assert retained_review_row(path, key) == before
    callback.assert_not_called()


@pytest.mark.parametrize("state,error", [
    ("COMPLETE", "ValueError: Reference record has missing or unexpected fields"),
    ("RUNNING", "ValueError: Reference record has missing or unexpected fields"),
    ("FAILED", "ValueError: Case blocker must select its matching current example"),
    ("FAILED", "TimeoutError: Synthetic timeout"),
])
def test_case_shape_recovery_rejects_other_states_or_errors(tmp_path, inputs, state, error):
    """Purpose: narrowly authorize only the observed failed schema record.
    Parameters: state/error. Returns: None. Failures: other failures get retried or altered.
    """
    supplied, _, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw, state=state, error=error)
    before = retained_review_row(path, key)
    with pytest.raises(ValueError, match="Only the diagnosed"):
        review.recover_case_reference_shape(path, key)
    assert retained_review_row(path, key) == before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_reference_recoveries").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["request", "contract", "no_alternative", "wrong_owner", "ready", "missing_reason"])
def test_case_shape_recovery_requires_current_binding_shape_and_valid_negative(tmp_path, inputs, monkeypatch, change):
    """Purpose: enforce request binding and all ordinary validation during recovery.
    Parameters: mutation. Returns: None. Failures: stale, unjustified or accepting recovery.
    """
    supplied, _, raw = alternate_case_response(inputs)
    if change == "no_alternative":
        raw["blocking_issues"][0]["evidence"] = {"case_ref": raw["blocking_issues"][0]["evidence"]["canonical_ref"]}
    elif change == "wrong_owner":
        raw["blocking_issues"][0]["evidence"]["case_ref"] = "C2"
    elif change == "ready":
        raw["outcome"] = "READY"
    elif change == "missing_reason":
        raw["blocking_issues"][0]["reason"] = ""
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    if change == "request":
        with sqlite3.connect(path) as db:
            request = json.loads(db.execute("SELECT request_json FROM independent_reviews_v2").fetchone()[0])
            request["prompt"] += " modified"
            db.execute("UPDATE independent_reviews_v2 SET request_json=?", (json.dumps(request),))
    elif change == "contract":
        monkeypatch.setattr(review, "CONTRACT", review.CONTRACT + "\nchanged-contract")
    before = retained_review_row(path, key)
    with pytest.raises(ValueError):
        review.recover_case_reference_shape(path, key)
    assert retained_review_row(path, key) == before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_reference_recoveries").fetchone()[0] == 0


@pytest.mark.parametrize("tamper", ["kind", "review_key", "raw_response_sha256", "canonical_sha256", "selections", "retained_raw"])
def test_case_shape_recovery_replay_rejects_audit_or_raw_tampering(tmp_path, inputs, tamper):
    """Purpose: check exact selected evidence on every recovered replay.
    Parameters: tampered field. Returns: None. Failures: altered audit/raw gets replayed or dispatched.
    """
    supplied, _, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    record = review.recover_case_reference_shape(path, key)
    with sqlite3.connect(path) as db:
        if tamper == "retained_raw":
            altered = deepcopy(raw)
            altered["blocking_issues"][0]["reason"] += " altered"
            db.execute("UPDATE independent_reviews_v2 SET response_json=?", (json.dumps(altered),))
        else:
            record[tamper] = [] if tamper == "selections" else "tampered"
            db.execute("UPDATE independent_review_reference_recoveries SET record_json=?", (json.dumps(record),))
    callback = Mock(side_effect=AssertionError("Tampered recovery must not dispatch"))
    with pytest.raises(RuntimeError, match="no longer matches retained evidence"):
        review.IndependentReviewer(path, callback).review(*supplied)
    callback.assert_not_called()


def test_case_shape_recovery_record_cannot_be_replaced(tmp_path, inputs):
    """Purpose: preserve immutable separate recovery audit records.
    Parameters: fixtures. Returns: None. Failures: repeated recovery overwrites a conflicting record.
    """
    supplied, _, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    record = review.recover_case_reference_shape(path, key)
    record["kind"] = "conflicting-record"
    retained = json.dumps(record)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE independent_review_reference_recoveries SET record_json=?", (retained,))
    with pytest.raises(ValueError, match="record is immutable"):
        review.recover_case_reference_shape(path, key)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT record_json FROM independent_review_reference_recoveries").fetchone()[0] == retained



@pytest.mark.parametrize("replacement", [{}, None, [], 0], ids=["empty-object", "null", "empty-list", "zero"])
def test_failed_case_replay_rejects_falsey_recovery_records(tmp_path, inputs, replacement):
    """Purpose: reject falsey saved recovery values without bypassing verification.
    Parameters: malformed replacement record. Returns: None. Failures: a FAILED
    row replays because its recovery JSON is empty/null/non-object or causes a call.
    """
    supplied, _, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    review.recover_case_reference_shape(path, key)
    before = retained_review_row(path, key)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE independent_review_reference_recoveries SET record_json=? WHERE review_key=?",
                   (json.dumps(replacement), key))
    callback = Mock(side_effect=AssertionError("Malformed recovery must not dispatch"))
    with pytest.raises(RuntimeError, match="no longer matches retained evidence"):
        review.IndependentReviewer(path, callback).review(*supplied)
    assert retained_review_row(path, key) == before
    callback.assert_not_called()


def test_failed_case_replay_rejects_nonzero_recovery_provider_calls(tmp_path, inputs):
    """Purpose: enforce the zero-call recovery audit. Parameters: local fixtures.
    Returns: None. Failures: an otherwise matching record with provider_calls=1
    replays, alters retained failure evidence or triggers another provider call.
    """
    supplied, _, raw = alternate_case_response(inputs)
    path = tmp_path / "case-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw)
    record = review.recover_case_reference_shape(path, key)
    before = retained_review_row(path, key)
    record["provider_calls"] = 1
    with sqlite3.connect(path) as db:
        db.execute("UPDATE independent_review_reference_recoveries SET record_json=? WHERE review_key=?",
                   (json.dumps(record), key))
    callback = Mock(side_effect=AssertionError("Nonzero-call recovery must not dispatch"))
    with pytest.raises(RuntimeError, match="no longer matches retained evidence"):
        review.IndependentReviewer(path, callback).review(*supplied)
    assert retained_review_row(path, key) == before
    callback.assert_not_called()



def decision_inputs(inputs):
    """Purpose: supply one nonliteral prior decision comparison. Parameters: inputs.
    Returns: detached inputs. Failures: none; semantic labels are explicit test choices.
    """
    supplied = deepcopy(inputs)
    supplied[0]["summary_mr"] = "Release only after a pilot passes."
    supplied[0]["action_mr"] = "Run a pilot before release."
    supplied[2].append({"id": "prior", "formula": "प्रमाणेन निर्णयः",
                        "decision_mr": "Launch once a pilot succeeds.",
                        "action_mr": "Pilot the product before launch."})
    return supplied


def decision_blocker(payload, identifier="prior", field="summary_mr"):
    """Purpose: select literal current decision evidence. Parameters: card/field.
    Returns: compact DUPLICATE_DECISION blocker. Failures: missing field ref fails.
    """
    return {"category": "DUPLICATE_DECISION", "draft_ref": find_ref(payload, "draft", field),
            "reason": "Both synthetic chapters require a passing pilot before release.",
            "evidence": {"comparator_id": identifier}}


def test_paired_decision_context_preserves_literals_and_only_normalizes_identity(inputs):
    """Purpose: expose both chapters without conflating paraphrases with identity.
    Parameters: fixture. Returns: None. Failures: lost evidence or inferred semantic equality.
    """
    supplied = decision_inputs(inputs)
    payload = selected_payload(supplied)
    paired = payload["decision_comparisons"]
    assert paired["current"] == {"decision_mr": supplied[0]["summary_mr"], "action_mr": supplied[0]["action_mr"]}
    assert paired["prior"] == [{**supplied[2][0], "same_formula": False, "identical_decision_and_action": False}]
    supplied[0]["summary_mr"] = "Café decision"
    supplied[0]["action_mr"] = "Record the test."
    supplied[2][0].update(decision_mr="  Cafe\u0301   decision ", action_mr="Record\tthe\ntest.")
    assert selected_payload(supplied)["decision_comparisons"]["prior"][0]["identical_decision_and_action"] is True
    supplied[2][0]["action_mr"] = "Record the test"
    assert selected_payload(supplied)["decision_comparisons"]["prior"][0]["identical_decision_and_action"] is False


def test_paraphrase_duplicate_materializes_current_literals_and_preserves_negative(inputs):
    """Purpose: support a reasoned semantic duplicate without generated evidence text.
    Parameters: fixture. Returns: None. Failures: paraphrase automatically passes or evidence is fabricated.
    """
    supplied = decision_inputs(inputs)
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", decision_checks={"prior": "SAME_DECISION"},
               blocking_issues=[decision_blocker(payload)])
    canonical, _ = materialize_review(raw, payload)
    assert set(raw) == {"decision_checks", "source_checks", "outcome", "blocking_issues", "advisory_notes", "uncertainties"}
    assert set(canonical) == {"source_checks", "outcome", "blocking_issues", "advisory_notes", "uncertainties"}
    assert canonical["blocking_issues"][0]["evidence"] == {
        "comparator_id": "prior", "same_decision": supplied[0]["summary_mr"], "same_action": supplied[0]["action_mr"]}
    assert review.validate_review(canonical, payload) == canonical
    raw.update(outcome="READY", blocking_issues=[])
    with pytest.raises(ValueError, match="matching duplication blocker"):
        materialize_review(raw, payload)


def test_distinct_decisions_can_share_theme_but_cannot_hide_duplicate_blocker(inputs):
    """Purpose: allow broad shared themes while enforcing relation consistency.
    Parameters: fixture. Returns: None. Failures: DISTINCT contains a duplication blocker.
    """
    supplied = decision_inputs(inputs)
    supplied[2][0].update(decision_mr="Investigate evidence before selecting a supplier.", action_mr="Compare supplier evidence.")
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    assert raw["decision_checks"] == {"prior": "DISTINCT"}
    canonical, _ = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    raw.update(outcome="REVISION_REQUIRED", blocking_issues=[decision_blocker(payload)])
    with pytest.raises(ValueError, match="Distinct decision contradicts"):
        materialize_review(raw, payload)


@pytest.mark.parametrize("identity,wrong_relation", [("formula", "DISTINCT"), ("formula", "SAME_DECISION"),
                                                      ("decision_action", "DISTINCT")])
def test_decision_map_cannot_omit_objective_formula_or_decision_identity(inputs, identity, wrong_relation):
    """Purpose: reject omitted objective comparison matches. Parameters: identity/relation.
    Returns: None. Failures: known formula or decision/action identity is labelled distinct.
    """
    supplied = decision_inputs(inputs)
    if identity == "formula":
        supplied[2][0]["formula"] = "। " + supplied[0]["new_sutra"] + " ॥"
    else:
        supplied[2][0].update(decision_mr=supplied[0]["summary_mr"], action_mr=supplied[0]["action_mr"])
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw["decision_checks"]["prior"] = wrong_relation
    with pytest.raises(ValueError, match="omitted an exact|missed identical"):
        materialize_review(raw, payload)


@pytest.mark.parametrize("checks", [{}, {"foreign": "DISTINCT"}, [], {"prior": "SIMILAR"}, {"prior": "EXACT_COPY"}])
def test_decision_map_rejects_omission_foreign_ids_array_unknown_or_false_copy(inputs, checks):
    """Purpose: enforce compact exhaustive map and justified exact-copy relations.
    Parameters: malformed map. Returns: None. Failures: omitted/foreign/invalid decisions pass.
    """
    payload = selected_payload(decision_inputs(inputs))
    raw = wire_response(payload)
    raw["decision_checks"] = deepcopy(checks)
    with pytest.raises(ValueError):
        materialize_review(raw, payload)


def test_decision_checks_sixth_root_is_mandatory(inputs):
    """Purpose: reject old five-root wire responses. Parameters: fixture.
    Returns: None. Failures: missing comparison decisions are silently defaulted.
    """
    payload = selected_payload(inputs)
    raw = wire_response(payload)
    del raw["decision_checks"]
    with pytest.raises(ValueError, match="exactly six"):
        materialize_review(raw, payload)


def test_decision_blocker_cross_id_and_extra_generated_evidence_are_rejected(inputs):
    """Purpose: keep duplicate evidence bound to exactly one supplied comparator.
    Parameters: fixture. Returns: None. Failures: foreign ID or generated same_action is accepted.
    """
    payload = selected_payload(decision_inputs(inputs))
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", decision_checks={"prior": "SAME_DECISION"}, blocking_issues=[decision_blocker(payload)])
    foreign = deepcopy(raw)
    foreign["blocking_issues"][0]["evidence"]["comparator_id"] = "foreign"
    with pytest.raises(ValueError, match="Unknown duplicated decision"):
        materialize_review(foreign, payload)
    raw["blocking_issues"][0]["evidence"]["same_action"] = "Invented supporting action"
    with pytest.raises(ValueError, match="missing or unexpected fields"):
        materialize_review(raw, payload)


@pytest.mark.parametrize("wrong_field", ["grammar_mr", "exposition.0"])
def test_duplicate_decision_ref_requires_decision_action_or_formula_field(inputs, wrong_field):
    """Purpose: prohibit irrelevant draft fields as duplicate evidence.
    Parameters: wrong field. Returns: None. Failures: another real draft selector bypasses anchoring.
    """
    payload = selected_payload(decision_inputs(inputs))
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", decision_checks={"prior": "SAME_DECISION"},
               blocking_issues=[decision_blocker(payload, field=wrong_field)])
    with pytest.raises(ValueError):
        materialize_review(raw, payload)
    for allowed in ("summary_mr", "action_mr", "new_sutra"):
        raw["blocking_issues"] = [decision_blocker(payload, field=allowed)]
        canonical, _ = materialize_review(raw, payload)
        assert review.validate_review(canonical, payload) == canonical


@pytest.mark.parametrize("field", ["summary_mr", "action_mr"])
@pytest.mark.parametrize("missing", [True, False])
def test_comparators_require_current_decision_and_action_before_callback(tmp_path, inputs, field, missing):
    """Purpose: fail missing/blank current decision context before any paid call.
    Parameters: absent field variant. Returns: None. Failures: incomplete inputs reach callback.
    """
    supplied = decision_inputs(inputs)
    if missing:
        supplied[0].pop(field)
    else:
        supplied[0][field] = " "
    callback = Mock(side_effect=AssertionError("Missing decision evidence cannot dispatch"))
    with pytest.raises(ValueError, match="requires current summary_mr and action_mr"):
        review.IndependentReviewer(tmp_path / "decisions.sqlite3", callback).review(*supplied)
    callback.assert_not_called()


def test_decision_context_tampering_and_duplicate_prior_ids_are_rejected(inputs):
    """Purpose: recompute paired facts and refuse collapsed comparator identities.
    Parameters: fixture. Returns: None. Failures: manipulated flags or duplicate IDs pass.
    """
    supplied = decision_inputs(inputs)
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    payload["decision_comparisons"]["prior"][0]["same_formula"] = True
    with pytest.raises(ValueError, match="context differs"):
        materialize_review(raw, payload)
    supplied[2].append(deepcopy(supplied[2][0]))
    with pytest.raises(ValueError, match="unique identities"):
        selected_payload(supplied)


def test_decision_map_is_cached_raw_and_returned_as_detached_audit(tmp_path, inputs):
    """Purpose: preserve raw six-field response and map metadata across zero-call replay.
    Parameters: temporary cache/fixture. Returns: None. Failures: lost map, extra API call,
    automatic PASS or mutable metadata leaking into cached evidence.
    """
    supplied = decision_inputs(inputs)
    payload = selected_payload(supplied)
    raw = wire_response(payload)
    raw.update(outcome="REVISION_REQUIRED", decision_checks={"prior": "SAME_DECISION"}, blocking_issues=[decision_blocker(payload)])
    original = deepcopy(raw)
    callback = Mock(return_value=raw)
    path = tmp_path / "decisions.sqlite3"
    first = review.IndependentReviewer(path, callback).review(*supplied)
    assert first["decision_comparisons"] == original["decision_checks"]
    assert first["verdict"] == "REVIEW_REQUIRED"
    assert json.loads(cached_rows(path)[0][1]) == original
    first["decision_comparisons"]["prior"] = "DISTINCT"
    no_call = Mock(side_effect=AssertionError("Replay cannot dispatch"))
    replay = review.IndependentReviewer(path, no_call).review(*supplied)
    assert replay["decision_comparisons"] == original["decision_checks"]
    assert replay["typed_review"] == materialize_review(original, payload)[0]
    callback.assert_called_once()
    no_call.assert_not_called()



def test_case_owner_alias_validates_and_audits_selected_owner(inputs):
    """Purpose: accept one unique explicit owner with a canonical hash audit.
    Parameters: fixture. Returns: None. Failures: owner inference changes verdict/raw evidence.
    """
    _, payload, raw = alternate_case_response(inputs)
    raw["blocking_issues"][0]["evidence"] = {"case_ref": "C1"}
    before = deepcopy(raw)
    canonical, audit = materialize_review(raw, payload)
    assert review.validate_review(canonical, payload) == canonical
    assert canonical["outcome"] == "REVISION_REQUIRED"
    assert canonical["blocking_issues"][0]["evidence"] == {"case_id": "C1", "canonical_quote": "The company ran a pilot."}
    assert {"response_path": "blocking_issues.0.evidence.case_ref",
            "ref": find_ref(payload, "case", "text_mr", "C1"), "selected_owner_id": "C1"} in audit
    assert raw == before


def test_case_owner_alias_rejects_another_current_case(inputs):
    """Purpose: preserve target-example ownership. Parameters: fixture.
    Returns: None. Failures: a valid other owner with identical text supports this case.
    """
    _, payload, raw = alternate_case_response(inputs)
    raw["blocking_issues"][0]["evidence"] = {"case_ref": "C2"}
    with pytest.raises(ValueError, match="matching current example"):
        materialize_review(raw, payload)


def test_case_owner_alias_rejects_unknown_stale_or_draft_hash(inputs):
    """Purpose: prevent treating arbitrary IDs/hash references as known owners.
    Parameters: fixture. Returns: None. Failures: nonexistent or wrong-kind IDs resolve.
    """
    _, payload, raw = alternate_case_response(inputs)
    for selected in ("unknown-business", "D000000000000", find_ref(payload, "draft", "examples.0.text_mr", "C1")):
        raw["blocking_issues"][0]["evidence"] = {"case_ref": selected}
        with pytest.raises(ValueError):
            materialize_review(raw, payload)


def test_case_owner_alias_rejects_ambiguous_canonical_owner(inputs):
    """Purpose: require exactly one canonical row for an owner alias.
    Parameters: fixture. Returns: None. Failures: multiple different facts for one owner are guessed.
    """
    supplied, _, raw = alternate_case_response(inputs)
    supplied[1]["examples"].append({"case_id": "C1", "text_mr": "Different canonical case facts."})
    payload = selected_payload(supplied)
    raw["blocking_issues"][0]["evidence"] = {"case_ref": "C1"}
    with pytest.raises(ValueError, match="uniquely identify"):
        materialize_review(raw, payload)


def test_case_owner_alias_known_failure_recovers_negative_without_calls(tmp_path, inputs):
    """Purpose: recover the diagnosed owner-only reference failure explicitly.
    Parameters: local cache/fixture. Returns: None. Failures: raw FAILED mutation,
    callback dispatch, missing selected-owner audit or promotion to PASS.
    """
    supplied, _, raw = alternate_case_response(inputs)
    raw["blocking_issues"][0]["evidence"] = {"case_ref": "C1"}
    path = tmp_path / "owner-recovery.sqlite3"
    key = seed_failed_case_shape(path, supplied, raw,
        error="ValueError: Unknown or wrong-kind evidence reference")
    before = retained_review_row(path, key)
    record = review.recover_case_reference_shape(path, key)
    assert record["provider_calls"] == 0
    assert any(row.get("selected_owner_id") == "C1" for row in record["selections"])
    callback = Mock(side_effect=AssertionError("Owner recovery must not dispatch"))
    result = review.IndependentReviewer(path, callback).review(*supplied)
    assert result["reference_recovery"] == record
    assert result["outcome"] == "REVISION_REQUIRED" and result["verdict"] == "REVIEW_REQUIRED"
    assert retained_review_row(path, key) == before
    callback.assert_not_called()
