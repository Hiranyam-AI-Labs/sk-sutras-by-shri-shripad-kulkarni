"""Offline v2 review contract tests; synthetic evidence and fake callbacks only.

Purpose: protect opinion isolation, evidence checks and durable one-call caching.
Parameters: pytest fixtures and synthetic records. Returns: test assertions only.
Failures: expose regressions to the parent; never invoke providers or a writer.
"""

import json
import sqlite3
from copy import deepcopy
from unittest.mock import Mock

import pytest

from src.orchestration import independent_review as review
from src.orchestration.research_council import ResearchCouncil


FORMULA = "विमतं पृष्ट्वा मार्गान् पश्येत्"
OPINIONS = {
    "peer_concerns": "PEER_OPINION_DO_NOT_SEND",
    "prior_review": "PRIOR_VERDICT_DO_NOT_SEND",
    "expected_outcome": "EXPECTED_LABEL_DO_NOT_SEND",
    "expected_labels": "EXPECTED_LABELS_DO_NOT_SEND",
    "expected": "EXPECTED_OBJECT_DO_NOT_SEND",
    "required_categories": "EXPECTED_CATEGORIES_DO_NOT_SEND",
}


@pytest.fixture
def evidence():
    """Purpose: provide synthetic complete review inputs. Parameters: none.
    Returns: draft, packet, cards. Failures: none; no disk or provider evidence.
    """
    sources = {
        "references": [{"id": "S1", "title": "Synthetic reference",
                        "original_text": "Ask questions before deciding.",
                        "meaning_mr": "निर्णयापूर्वी प्रश्न विचारा."}],
        "examples": [{"case_id": "C1", "entity": "Synthetic business",
                      "text_mr": "संस्थेने चाचणीनंतर निर्णय घेतला."}],
    }
    draft = {
        "id": "entry-5", "number": 5, "chapter": 2, "title_mr": "निर्णय तपासा",
        "new_sutra": FORMULA, "grammar_mr": "वाक्याचे व्याकरण तपासा.",
        "translation_mr": "विरोधी मत विचारून पर्याय पाहा.",
        "exposition": ["विचार " * 500],
        "references": deepcopy(sources["references"]),
        "examples": deepcopy(sources["examples"]),
        "comparative_mr": [{"source_id": "S1", "explanation_mr": "आधुनिक उपयोग."}],
        "case_ids": ["C1"], "dos_mr": ["प्रश्न विचारा."],
        "donts_mr": ["घाई टाळा."], "application_mr": "निर्णयापूर्वी पर्याय तपासा.",
        "action_mr": "विरोधी मत नोंदवा.", "summary_mr": "विचारपूर्वक निर्णय घ्या.",
    }
    cards = [{"id": "entry-2", "formula": "प्रमाणेन निर्णयः",
              "decision_mr": "पुरावा मिळाल्यावर निर्णय घ्या.",
              "action_mr": "चाचणी नोंदवा."}]
    return draft, sources, cards


def answer(outcome="READY", issues=None, notes=None, uncertainties=None, source_checks=None):
    """Purpose: construct a fake review. Parameters: outcome and evidence lists.
    Returns: fresh JSON dictionary. Failures: none; invalid cases are intentional.
    """
    return {"outcome": outcome, "blocking_issues": deepcopy(issues or []),
            "advisory_notes": list(notes or []), "uncertainties": deepcopy(uncertainties or []),
            "source_checks": deepcopy([source_check()] if source_checks is None else source_checks)}




def source_check(classification="QUALIFIED_ANALOGY", *, field="comparative_mr.0.explanation_mr",
                 source_id="S1", claim="", application="आधुनिक उपयोग.",
                 source_quote="Ask questions before deciding."):
    """Purpose: build one synthetic source disposition. Parameters: literal evidence.
    Returns: seven-field source check. Failures: none; tests deliberately alter it.
    """
    return {"field": field, "source_id": source_id, "source_claim_quote": claim,
            "application_quote": application, "source_quote": source_quote,
            "classification": classification, "reason": "Synthetic source/claim comparison for schema testing."}


def uncertainty(field="new_sutra", quote=FORMULA):
    """Purpose: anchor a scholarly question to current text. Parameters: field/quote.
    Returns: structured uncertainty. Failures: none; tests may alter its evidence.
    """
    return {"category": "LEXICAL_AMBIGUITY", "field": field, "quote": quote,
            "question": "Does मार्गान् function as the direct object of पश्येत् under the supplied grammatical explanation?"}


def issue(category, evidence, field="new_sutra", quote=FORMULA):
    """Purpose: construct a current-text blocker. Parameters: category and evidence.
    Returns: JSON issue. Failures: none; tests validate substantive predicates.
    """
    return {"category": category, "field": field, "quote": quote,
            "reason": "Synthetic substantive defect for contract validation.",
            "evidence": deepcopy(evidence)}


def rows(path):
    """Purpose: inspect the temporary audit. Parameters: SQLite path.
    Returns: persisted review rows. Failures: SQLite errors expose broken storage.
    """
    with sqlite3.connect(path) as db:
        return db.execute("SELECT review_key,state,request_json,response_json,error "
                          "FROM independent_reviews_v2 ORDER BY rowid").fetchall()


def reference_answer(canonical, payload, decision_checks=None):
    """Map known canonical test fixtures to the actual reference-only wire schema.

    Parameters: synthetic answer and the supplied prompt payload. Returns: detached
    ID selections, never generated quotations. Missing literal fixture evidence
    becomes an unknown ID so the real production resolver must reject it. This
    Explicit fixture blockers select EXACT_COPY/SAME_DECISION; remaining synthetic
    comparators are declared DISTINCT. An optional map permits deliberate invalid
    cases. This helper never repairs omitted count/copy findings or materializes,
    validates or normalizes a production response.
    """
    catalog = payload["evidence_selection"]["catalog"]

    def select(kind, text=None, *, field=None, owner=None, whole=False):
        """Select exact fixture text/ownership; unknown evidence stays invalid.
        Parameters: typed constraints. Returns: catalog ID or unknown sentinel.
        Multiple identical sentence/whole candidates prefer the whole passage.
        """
        matches = [(key, row) for key, row in catalog.items()
                   if row["kind"] == kind
                   and (text is None or row["text"] == text)
                   and (field is None or row["field"] == field)
                   and (owner is None or row["owner_id"] == owner)
                   and (not whole or row["scope"] == "whole")]
        matches.sort(key=lambda item: (item[1]["scope"] != "whole", item[0]))
        return matches[0][0] if matches else "UNKNOWN_FIXTURE_EVIDENCE"

    wire = deepcopy(canonical)
    if decision_checks is None:
        decision_checks = {card["id"]: "DISTINCT" for card in payload["comparison_chapters"]}
        for blocker in canonical["blocking_issues"]:
            if blocker["category"] in {"EXACT_COPY", "DUPLICATE_DECISION"}:
                comparator_id = blocker["evidence"]["comparator_id"]
                decision_checks[comparator_id] = ("EXACT_COPY" if blocker["category"] == "EXACT_COPY"
                                                   else "SAME_DECISION")
    wire["decision_checks"] = deepcopy(decision_checks)
    wire["source_checks"] = [{
        "comparison_ref": select("draft", field=check["field"],
                                 owner=check["source_id"], whole=True),
        "source_claim_ref": (select("draft", check["source_claim_quote"],
                                    field=check["field"], owner=check["source_id"])
                             if check["source_claim_quote"] else None),
        "application_ref": (select("draft", check["application_quote"],
                                   field=check["field"], owner=check["source_id"])
                            if check["application_quote"] else None),
        "source_ref": select("source", check["source_quote"], owner=check["source_id"]),
        "classification": check["classification"], "reason": check["reason"],
    } for check in canonical["source_checks"]]
    wire["blocking_issues"] = []
    for blocker in canonical["blocking_issues"]:
        proof = deepcopy(blocker["evidence"])
        if blocker["category"] == "SOURCE_DISTORTION":
            proof = {"source_ref": select("source", proof["source_quote"],
                                          owner=proof["source_id"])}
        elif blocker["category"] == "CASE_FACT":
            proof = {"case_ref": select("case", proof["canonical_quote"],
                                        owner=proof["case_id"])}
        elif blocker["category"] == "DUPLICATE_DECISION":
            proof = {"comparator_id": proof["comparator_id"]}
        wire["blocking_issues"].append({
            "category": blocker["category"],
            "draft_ref": select("draft", blocker["quote"], field=blocker["field"]),
            "reason": blocker["reason"], "evidence": proof,
        })
    wire["uncertainties"] = [{
        "category": item["category"],
        "draft_ref": select("draft", item["quote"], field=item["field"]),
        "question": item["question"],
    } if isinstance(item, dict) else deepcopy(item) for item in canonical["uncertainties"]]
    return wire


def reference_callback(canonical, decision_checks=None):
    """Create a fake provider selecting IDs from its actual received prompt.

    Parameters: canonical fixture and optional synthetic decision map. Returns: Mock with wire_responses
    recording exact returned objects. Bad prompt/schema fails locally; no API,
    production codec patch, canonical validation or expected-outcome rewriting.
    """
    responses = []

    def respond(system, prompt):
        """Parse the supplied evidence and return fixture-selected references.
        Inputs are callback strings; output is reference-only JSON. Invalid JSON
        raises rather than supplying fallback quotes or guessing evidence.
        """
        payload = json.loads(prompt.rsplit("\nEVIDENCE\n", 1)[1])
        wire = reference_answer(canonical, payload, decision_checks)
        responses.append(deepcopy(wire))
        return wire

    callback = Mock(side_effect=respond)
    callback.wire_responses = responses
    return callback


def test_payload_drops_top_level_opinions_and_expected_labels(evidence):
    """Purpose: prevent opinion priming. Parameters: synthetic evidence fixture.
    Returns: None. Failures: leaked extra input labels or missing evidence.
    """
    draft, sources, cards = deepcopy(evidence)
    for record in (draft, sources, cards[0]):
        record.update(OPINIONS)
    payload = review.build_payload(draft, sources, cards)
    encoded = json.dumps(payload, ensure_ascii=False)
    assert all(marker not in encoded for marker in OPINIONS.values())
    assert payload["current_draft"]["new_sutra"] == FORMULA
    assert payload["canonical_sources"]["references"][0]["id"] == "S1"
    assert payload["comparison_chapters"][0]["decision_mr"] == cards[0]["decision_mr"]


@pytest.mark.parametrize("container,field", [
    (0, "references"), (0, "examples"), (1, "references"), (1, "examples"),
])
def test_payload_drops_nested_opinion_metadata(evidence, container, field):
    """Purpose: prevent nested reference/case opinion leakage. Parameters: location.
    Returns: None. Failures: any peer, prior-review or expected-label marker leaks.
    """
    supplied = deepcopy(evidence)
    supplied[container][field][0].update(OPINIONS)
    payload = review.build_payload(*supplied)
    encoded = json.dumps(payload, ensure_ascii=False)
    assert all(marker not in encoded for marker in OPINIONS.values())
    assert supplied[container][field][0]["prior_review"] == OPINIONS["prior_review"]


def test_payload_is_deeply_detached_from_inputs(evidence):
    """Purpose: preserve original draft/case evidence. Parameters: fixture.
    Returns: None. Failures: caller data aliases the returned reviewer payload.
    """
    original = deepcopy(evidence)
    payload = review.build_payload(*evidence)
    payload["current_draft"]["exposition"][0] = "changed"
    payload["canonical_sources"]["examples"][0]["text_mr"] = "changed"
    payload["comparison_chapters"][0]["formula"] = "changed"
    assert evidence == original


def test_same_full_payload_replays_once_across_instances(tmp_path, evidence):
    """Purpose: preserve paid review cache. Parameters: temporary DB and evidence.
    Returns: None. Failures: repeated callback, lost notes, mutated input or audit.
    """
    original = deepcopy(evidence)
    path = tmp_path / "review.sqlite3"
    callback = reference_callback(answer(notes=["Optional editorial suggestion."]))
    first = review.IndependentReviewer(path, callback).review(*evidence)
    first["typed_review"]["advisory_notes"].append("caller mutation")
    forbidden_call = Mock(side_effect=AssertionError("Cached review must not call a provider"))
    cached = review.IndependentReviewer(path, forbidden_call).review(*deepcopy(evidence))
    callback.assert_called_once()
    forbidden_call.assert_not_called()
    assert cached["review_key"] == first["review_key"]
    assert cached["typed_review"]["advisory_notes"] == ["Optional editorial suggestion."]
    assert cached["reviewed_draft_sha256"] == review.canonical_hash(evidence[0])
    assert evidence == original
    persisted = rows(path)
    assert len(persisted) == 1 and persisted[0][1] == "COMPLETE"
    request = json.loads(persisted[0][2])
    assert request["system"] == callback.call_args.args[0]
    assert request["prompt"] == callback.call_args.args[1]
    assert request["contract_hash"] == review.contract_hash()


@pytest.mark.parametrize("setting", ["SYSTEM", "CONTRACT", "MODEL", "VERSION"])
def test_contract_identity_change_never_reuses_old_review(tmp_path, evidence, monkeypatch, setting):
    """Purpose: bind rubric/model/full prompt changes. Parameters: setting and fixtures.
    Returns: None. Failures: changed contract reuses a cached verdict.
    """
    path = tmp_path / "review.sqlite3"
    callback = reference_callback(answer())
    reviewer = review.IndependentReviewer(path, callback)
    before_hash = review.contract_hash()
    before = reviewer.review(*evidence)
    monkeypatch.setattr(review, setting, getattr(review, setting) + "\nchanged-contract")
    assert review.contract_hash() != before_hash
    after = reviewer.review(*evidence)
    replay = reviewer.review(*evidence)
    assert before["review_key"] != after["review_key"] == replay["review_key"]
    assert callback.call_count == 2
    assert len(rows(path)) == 2
    if setting == "SYSTEM":
        assert callback.call_args_list[0].args[0] != callback.call_args_list[1].args[0]
    if setting == "CONTRACT":
        assert callback.call_args_list[0].args[1] != callback.call_args_list[1].args[1]


@pytest.mark.parametrize("changed_file", ["independent_review.py", "review_evidence.py"])
def test_calibration_implementation_identity_binds_reviewer_and_resolver(tmp_path, monkeypatch, changed_file):
    """Purpose: invalidate calibration when either production implementation changes.
    Parameters: temporary source files and changed filename. Returns: None.
    Failures: resolver changes escape identity checks or untouched files hash unstably.
    """
    for name in ("independent_review.py", "review_evidence.py"):
        (tmp_path / name).write_text("# synthetic implementation\n", encoding="utf-8")
    monkeypatch.setattr(review, "__file__", str(tmp_path / "independent_review.py"))
    before = review.implementation_hash()
    rubric = review.contract_hash()
    assert review.implementation_hash() == before
    (tmp_path / changed_file).write_text("# changed synthetic implementation\n", encoding="utf-8")
    assert review.implementation_hash() != before
    assert review.contract_hash() == rubric


@pytest.mark.parametrize("changed", ["draft", "source", "comparison", "decision"])
def test_changed_evidence_gets_distinct_cache_key(tmp_path, evidence, changed):
    """Purpose: prevent stale evidence reuse. Parameters: changed evidence kind.
    Returns: None. Failures: changed input shares an old result or repeats on replay.
    """
    callback = reference_callback(answer())
    reviewer = review.IndependentReviewer(tmp_path / "review.sqlite3", callback)
    original = reviewer.review(*evidence, decision="Original business decision")
    draft, sources, cards = deepcopy(evidence)
    decision = "Original business decision"
    if changed == "draft":
        draft["action_mr"] += " अतिरिक्त चाचणी करा."
    elif changed == "source":
        sources["references"][0]["meaning_mr"] += " पुरावा तपासा."
    elif changed == "comparison":
        cards[0]["decision_mr"] += " खर्च तपासा."
    else:
        decision = "Different business decision"
    modified = reviewer.review(draft, sources, cards, decision=decision)
    assert modified["review_key"] != original["review_key"]
    assert reviewer.review(draft, sources, cards, decision=decision) == modified
    assert reviewer.review(*evidence, decision="Original business decision") == original
    assert callback.call_count == 2


def test_v26_decision_wire_keeps_fixture_judgments_and_server_bound_evidence(tmp_path, evidence):
    """Purpose: exercise DISTINCT, SAME_DECISION and EXACT_COPY through production.
    Parameters: synthetic inputs and temporary cache. Returns: None. Failures:
    omitted comparisons, model-authored duplicate evidence, lost holds or paid replay.
    """
    draft, sources, cards = deepcopy(evidence)
    cards.extend([
        {"id": "same-business", "formula": "विवेकेन निर्णयः", "decision_mr": draft["summary_mr"],
         "action_mr": draft["action_mr"]},
        {"id": "literal-copy", "formula": draft["new_sutra"],
         "decision_mr": "वेगळा कृतीसंदर्भ.", "action_mr": "नोंदी तपासा."},
    ])
    duplicate = issue("DUPLICATE_DECISION", {
        "comparator_id": "same-business", "same_decision": "Provider prose must not enter the wire",
        "same_action": "Provider prose must not replace the current action",
    })
    copied = issue("EXACT_COPY", {"comparator_id": "literal-copy"})
    canonical = answer("REVISION_REQUIRED", issues=[duplicate, copied])
    frozen = deepcopy(canonical)
    callback = reference_callback(canonical)
    path = tmp_path / "decisions.sqlite3"
    result = review.IndependentReviewer(path, callback).review(draft, sources, cards)
    wire = callback.wire_responses[0]
    assert set(wire) == {"decision_checks", "source_checks", "outcome", "blocking_issues",
                         "advisory_notes", "uncertainties"}
    assert wire["decision_checks"] == {"entry-2": "DISTINCT", "same-business": "SAME_DECISION",
                                       "literal-copy": "EXACT_COPY"}
    assert wire["blocking_issues"][0]["evidence"] == {"comparator_id": "same-business"}
    assert "Provider prose" not in json.dumps(wire)
    assert result["typed_review"]["blocking_issues"][0]["evidence"] == {
        "comparator_id": "same-business", "same_decision": draft["summary_mr"],
        "same_action": draft["action_mr"],
    }
    assert set(result["typed_review"]) == set(canonical)
    assert result["decision_comparisons"] == wire["decision_checks"]
    assert result["outcome"] == "REVISION_REQUIRED" and result["verdict"] == "REVIEW_REQUIRED"
    assert json.loads(rows(path)[0][3]) == wire
    assert canonical == frozen
    no_call = Mock(side_effect=AssertionError("Decision replay cannot dispatch"))
    assert review.IndependentReviewer(path, no_call).review(draft, sources, cards) == result
    callback.assert_called_once()
    no_call.assert_not_called()


@pytest.mark.parametrize("decision_checks", [
    {}, {"entry-2": "DISTINCT", "foreign": "DISTINCT"},
    {"entry-2": "UNSUPPORTED_LABEL"}, {"entry-2": "SAME_DECISION"},
])
def test_v26_invalid_decision_map_is_saved_failed_without_retry(tmp_path, evidence, decision_checks):
    """Purpose: make missing, foreign or unsupported judgments terminal at dispatch.
    Parameters: deliberately inconsistent map. Returns: None. Failures: inferred
    labels/blockers, absent raw evidence, silent PASS or another callback.
    """
    callback = reference_callback(answer(), decision_checks=decision_checks)
    path = tmp_path / "decisions.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized") as failure:
        review.IndependentReviewer(path, callback).review(*evidence)
    assert isinstance(failure.value.__cause__, ValueError)
    assert "Decision" in str(failure.value.__cause__) or "decision" in str(failure.value.__cause__)
    assert rows(path)[0][1] == "FAILED"
    assert json.loads(rows(path)[0][3]) == callback.wire_responses[0]
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    callback.assert_called_once()


def test_v26_rejects_old_five_root_reference_wire(tmp_path, evidence):
    """Purpose: reject v2.5 reference answers that omit all decision judgments.
    Parameters: temporary cache and synthetic evidence. Returns: None. Failures:
    silent insertion of DISTINCT labels or loss of the original malformed answer.
    """
    wire = reference_answer(answer(), review.build_payload(*evidence))
    del wire["decision_checks"]
    callback = Mock(return_value=wire)
    path = tmp_path / "old-wire.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized") as failure:
        review.IndependentReviewer(path, callback).review(*evidence)
    assert "exactly six root fields" in str(failure.value.__cause__)
    assert rows(path)[0][1] == "FAILED"
    assert json.loads(rows(path)[0][3]) == wire
    callback.assert_called_once()


def test_v26_no_prior_chapters_uses_empty_decision_map(tmp_path, evidence):
    """Purpose: represent no comparison work as an explicit empty map.
    Parameters: fixture without prior cards. Returns: None. Failures: invented
    comparator labels or leakage of the sixth wire field into canonical validation.
    """
    draft, sources, _ = deepcopy(evidence)
    callback = reference_callback(answer())
    result = review.IndependentReviewer(tmp_path / "empty.sqlite3", callback).review(draft, sources, [])
    assert callback.wire_responses[0]["decision_checks"] == {}
    assert result["typed_review"] == answer()
    assert result["decision_comparisons"] == {}
    callback.assert_called_once()


@pytest.mark.parametrize("field", ["summary_mr", "action_mr"])
@pytest.mark.parametrize("missing", [False, True])
def test_v26_missing_current_decision_evidence_stops_before_callback(tmp_path, evidence, field, missing):
    """Purpose: require current decision/action before comparing prior chapters.
    Parameters: missing or blank field. Returns: None. Failures: a callback runs
    without substantive comparison context or a RUNNING attempt is persisted.
    """
    draft, sources, cards = deepcopy(evidence)
    if missing:
        del draft[field]
    else:
        draft[field] = "  "
    no_call = Mock(side_effect=AssertionError("Incomplete comparisons cannot dispatch"))
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(ValueError, match="requires current summary_mr and action_mr"):
        review.IndependentReviewer(path, no_call).review(draft, sources, cards)
    no_call.assert_not_called()
    assert rows(path) == []


def test_invalid_review_is_failed_and_never_automatically_repeated(tmp_path, evidence):
    """Purpose: make invalid output terminal. Parameters: temporary DB and evidence.
    Returns: None. Failures: schema failure is retried, lost, or changed into PASS.
    """
    path = tmp_path / "review.sqlite3"
    invalid = answer("READY", uncertainties=[uncertainty()])
    callback = reference_callback(invalid)
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*evidence)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    callback.assert_called_once()
    persisted = rows(path)
    assert len(persisted) == 1 and persisted[0][1] == "FAILED"
    assert json.loads(persisted[0][3]) == callback.wire_responses[0]
    assert "ValueError" in persisted[0][4]


def test_forged_fixture_quote_yields_unknown_ref_and_durable_failure(tmp_path, evidence):
    """Purpose: ensure fixture conversion cannot fabricate matching evidence.
    Parameters: temporary cache and synthetic inputs. Returns: None. Failures:
    guessed references, discarded raw failure or automatic second callback.
    """
    canonical = answer("AUTHOR_REVIEW", uncertainties=[uncertainty(quote="invented passage")])
    callback = reference_callback(canonical)
    path = tmp_path / "unknown-ref.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized") as failure:
        review.IndependentReviewer(path, callback).review(*evidence)
    assert "Unknown or wrong-kind" in str(failure.value.__cause__)
    wire = callback.wire_responses[0]
    assert wire["uncertainties"][0]["draft_ref"] == "UNKNOWN_FIXTURE_EVIDENCE"
    assert "invented passage" not in json.dumps(wire)
    assert rows(path)[0][1] == "FAILED"
    assert json.loads(rows(path)[0][3]) == wire
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    callback.assert_called_once()


def test_complete_cache_cannot_replay_legacy_quote_format(tmp_path, evidence):
    """Purpose: enforce the reference wire on successful-cache replay as well.
    Parameters: temporary cache and synthetic inputs. Returns: None. Failures:
    cached quote responses bypass materialization or trigger a replacement call.
    """
    path = tmp_path / "review.sqlite3"
    callback = reference_callback(answer())
    review.IndependentReviewer(path, callback).review(*evidence)
    with sqlite3.connect(path) as db:
        legacy_quotes = {**answer(), "decision_checks": {"entry-2": "DISTINCT"}}
        db.execute("UPDATE independent_reviews_v2 SET response_json=?", (json.dumps(legacy_quotes),))
    before = rows(path)
    no_call = Mock(side_effect=AssertionError("Malformed cached response cannot dispatch"))
    with pytest.raises(ValueError, match="Reference record"):
        review.IndependentReviewer(path, no_call).review(*evidence)
    assert rows(path) == before
    no_call.assert_not_called()


def test_false_four_word_objection_raises_and_cannot_rewrite(tmp_path, evidence, monkeypatch):
    """Purpose: reject invented word-limit defects. Parameters: fixtures.
    Returns: None. Failures: a valid four-word formula triggers a writer or PASS.
    """
    blocker = issue("MECHANICAL", {"rule": "word_limit"})
    rejected = answer("REVISION_REQUIRED", issues=[blocker])
    assert len(FORMULA.split()) == 4 and len(FORMULA) <= 32
    with pytest.raises(ValueError, match="Mechanical objection contradicted"):
        review.validate_review(rejected, review.build_payload(*evidence))
    writer = Mock(side_effect=AssertionError("Invalid review must not invoke a writer"))
    monkeypatch.setattr(ResearchCouncil, "_compose", writer)
    path = tmp_path / "review.sqlite3"
    callback = reference_callback(rejected)
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*evidence)
    assert rows(path)[0][1] == "FAILED"
    callback.assert_called_once()
    writer.assert_not_called()


def test_valid_mechanical_negative_remains_revision_required(tmp_path, evidence):
    """Purpose: preserve substantiated rejection. Parameters: fixtures.
    Returns: None. Failures: actual five-word defect becomes PASS or rewrites text.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["new_sutra"] = "एकं द्वे त्रीणि चत्वारि पञ्च"
    frozen = deepcopy(draft)
    blocker = issue("MECHANICAL", {"rule": "word_limit"}, quote=draft["new_sutra"])
    callback = reference_callback(answer("REVISION_REQUIRED", issues=[blocker]))
    reviewer = review.IndependentReviewer(tmp_path / "review.sqlite3", callback)
    result = reviewer.review(draft, sources, cards)
    assert result["verdict"] == "REVIEW_REQUIRED"
    assert result["outcome"] == "REVISION_REQUIRED"
    assert result["typed_review"]["blocking_issues"] == [blocker]
    assert draft == frozen
    assert reviewer.review(draft, sources, cards) == result
    callback.assert_called_once()


@pytest.mark.parametrize("same", [False, True])
def test_exact_copy_requires_actual_matching_formula(evidence, same):
    """Purpose: verify literal-copy evidence. Parameters: comparator match flag.
    Returns: None. Failures: unrelated formula accepted as exact-copy evidence.
    """
    draft, sources, cards = deepcopy(evidence)
    if same:
        cards[0]["formula"] = "। " + FORMULA.replace(" ", "  ") + " ॥"
    rejected = answer("REVISION_REQUIRED", issues=[issue("EXACT_COPY", {"comparator_id": "entry-2"})])
    payload = review.build_payload(draft, sources, cards)
    if same:
        assert review.validate_review(rejected, payload) == rejected
    else:
        with pytest.raises(ValueError, match="Exact-copy objection contradicted"):
            review.validate_review(rejected, payload)


@pytest.mark.parametrize("category", ["MECHANICAL", "EXACT_COPY", "DUPLICATE_DECISION",
                                     "SOURCE_DISTORTION", "CASE_FACT", "GRAMMAR", "UNSUPPORTED_CLAIM"])
@pytest.mark.parametrize("missing", [None, {}])
def test_category_evidence_is_required(evidence, category, missing):
    """Purpose: reject unsupported category labels. Parameters: category/evidence.
    Returns: None. Failures: a typed blocker passes without its required evidence.
    """
    rejected = answer("REVISION_REQUIRED", issues=[issue(category, missing)])
    with pytest.raises(ValueError, match="evidence missing"):
        review.validate_review(rejected, review.build_payload(*evidence))


@pytest.mark.parametrize("category,proof", [
    ("DUPLICATE_DECISION", {"comparator_id": "entry-2", "same_decision": "Same release decision"}),
    ("SOURCE_DISTORTION", {"source_id": "S1"}),
    ("CASE_FACT", {"case_id": "C1"}),
    ("GRAMMAR", {"rule": "agreement"}),
    ("UNSUPPORTED_CLAIM", {"claim_type": "invented_fact"}),
])
def test_partial_category_evidence_is_not_enough(evidence, category, proof):
    """Purpose: require category-specific reasoning. Parameters: incomplete proof.
    Returns: None. Failures: identifier/quote alone substitutes for required evidence.
    """
    with pytest.raises(ValueError, match="evidence missing"):
        review.validate_review(answer("REVISION_REQUIRED", issues=[issue(category, proof)]),
                               review.build_payload(*evidence))


@pytest.mark.parametrize("category,proof", [
    ("EXACT_COPY", {"comparator_id": "absent"}),
    ("SOURCE_DISTORTION", {"source_id": "S1", "source_quote": "Not in the source", "contradiction": "Conflict"}),
    ("CASE_FACT", {"case_id": "C1", "canonical_quote": "Not in the case", "contradiction": "Conflict"}),
])
def test_external_evidence_must_exist_literally(evidence, category, proof):
    """Purpose: reject fabricated canonical support. Parameters: invalid proof.
    Returns: None. Failures: absent comparator, source passage or case quote passes.
    """
    with pytest.raises(ValueError):
        review.validate_review(answer("REVISION_REQUIRED", issues=[issue(category, proof)]),
                               review.build_payload(*evidence))


def test_valid_source_negative_preserves_typed_evidence(evidence):
    """Purpose: accept evidence-grounded negative structure. Parameters: fixture.
    Returns: None. Failures: a valid negative loses its current/canonical quote.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["exposition"][0] = "The source says never ask questions. " + draft["exposition"][0]
    blocker = issue("SOURCE_DISTORTION", {
        "source_id": "S1", "source_quote": "Ask questions before deciding.",
        "contradiction": "The draft reverses the supplied source's instruction to ask questions.",
    }, field="exposition.0", quote="The source says never ask questions.")
    rejected = answer("REVISION_REQUIRED", issues=[blocker])
    assert review.validate_review(rejected, review.build_payload(draft, sources, cards)) == rejected


def test_blocker_must_quote_current_field(evidence):
    """Purpose: reject obsolete proposal criticism. Parameters: fixture.
    Returns: None. Failures: nonexistent current quote is accepted as evidence.
    """
    blocker = issue("GRAMMAR", {"rule": "agreement", "explanation": "Synthetic rule application"},
                    quote="obsolete proposal text")
    with pytest.raises(ValueError, match="quote absent"):
        review.validate_review(answer("REVISION_REQUIRED", issues=[blocker]), review.build_payload(*evidence))


@pytest.mark.parametrize("uncertain", [False, True])
def test_advisory_ready_and_author_review_have_distinct_gates(tmp_path, evidence, uncertain):
    """Purpose: preserve advice versus uncertainty. Parameters: uncertainty flag.
    Returns: None. Failures: advice blocks READY or uncertainty becomes PASS.
    """
    raw = answer("AUTHOR_REVIEW" if uncertain else "READY", notes=["Optional style suggestion."],
                 uncertainties=[uncertainty()] if uncertain else [])
    callback = reference_callback(raw)
    result = review.IndependentReviewer(tmp_path / "review.sqlite3", callback).review(*evidence)
    assert result["verdict"] == ("REVIEW_REQUIRED" if uncertain else "PASS")
    assert result["outcome"] == raw["outcome"]
    assert result["typed_review"] == raw
    assert bool(result["issues"]) is uncertain
    if uncertain:
        held = result["issues"][0]
        assert held["field"] == "new_sutra" and held["quote"] == FORMULA
        assert held["reason"] == raw["uncertainties"][0]["question"]
    callback.assert_called_once()


def test_reviewer_cannot_return_an_edited_draft(tmp_path, evidence):
    """Purpose: prevent validator editing. Parameters: temporary DB and evidence.
    Returns: None. Failures: returned draft patch passes or mutates original data.
    """
    original = deepcopy(evidence)
    raw = {**answer(), "draft": {"new_sutra": "rewritten"}}
    path = tmp_path / "review.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, reference_callback(raw)).review(*evidence)
    assert evidence == original
    assert rows(path)[0][1] == "FAILED"


def test_callback_failure_does_not_trigger_writer_or_repeat(tmp_path, evidence, monkeypatch):
    """Purpose: stop provider failures without composition. Parameters: fixtures.
    Returns: None. Failures: callback error triggers writer, retry or missing audit.
    """
    writer = Mock(side_effect=AssertionError("A failed validator cannot invoke composition"))
    monkeypatch.setattr(ResearchCouncil, "_compose", writer)
    callback = Mock(side_effect=TimeoutError("Synthetic validator timeout"))
    path = tmp_path / "review.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized") as failure:
        review.IndependentReviewer(path, callback).review(*evidence)
    assert isinstance(failure.value.__cause__, TimeoutError)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    callback.assert_called_once()
    writer.assert_not_called()
    persisted = rows(path)
    assert len(persisted) == 1 and persisted[0][1] == "FAILED"
    assert "TimeoutError" in persisted[0][4]


@pytest.mark.parametrize("generic", [
    "New formula requires scholar review.",
    "Not a verbatim quotation from an ancient source.",
    "The formula is unfamiliar and its grammar is uncertain.",
])
def test_generic_uncertainty_strings_are_invalid(evidence, generic):
    """Purpose: reject unanchored generic holds. Parameters: fixture and string.
    Returns: None. Failures: vague novelty/nonverbatim concerns become a valid hold.
    """
    with pytest.raises(ValueError):
        review.validate_review(answer("AUTHOR_REVIEW", uncertainties=[generic]),
                               review.build_payload(*evidence))


@pytest.mark.parametrize("missing", ["category", "field", "quote", "question"])
def test_uncertainty_requires_all_three_evidence_fields(evidence, missing):
    """Purpose: require grounded questions. Parameters: fixture and missing key.
    Returns: None. Failures: incomplete structured uncertainty is accepted.
    """
    question = uncertainty()
    question.pop(missing)
    with pytest.raises(ValueError):
        review.validate_review(answer("AUTHOR_REVIEW", uncertainties=[question]),
                               review.build_payload(*evidence))


@pytest.mark.parametrize("changes", [
    {"field": "absent_field"}, {"quote": "obsolete proposal"},
    {"quote": ""}, {"question": " "},
])
def test_uncertainty_must_quote_current_field_and_ask_question(evidence, changes):
    """Purpose: reject stale or empty uncertainty evidence. Parameters: bad fields.
    Returns: None. Failures: ungrounded scholarly question passes validation.
    """
    question = {**uncertainty(), **changes}
    with pytest.raises(ValueError):
        review.validate_review(answer("AUTHOR_REVIEW", uncertainties=[question]),
                               review.build_payload(*evidence))


def test_generic_uncertainty_is_durable_failure_not_writer_request(tmp_path, evidence, monkeypatch):
    """Purpose: stop invalid scholarly holds without rewrites. Parameters: fixtures.
    Returns: None. Failures: generic uncertainty triggers retry, writer or PASS.
    """
    writer = Mock(side_effect=AssertionError("Invalid uncertainty cannot request composition"))
    monkeypatch.setattr(ResearchCouncil, "_compose", writer)
    callback = reference_callback(answer("AUTHOR_REVIEW", uncertainties=["Nonverbatim formula needs scholar approval."]))
    path = tmp_path / "review.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*evidence)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    assert rows(path)[0][1] == "FAILED"
    callback.assert_called_once()
    writer.assert_not_called()


@pytest.mark.parametrize("category", ["LEXICAL_AMBIGUITY", "SOURCE_EDITION", "CONFLICTING_EVIDENCE"])
def test_allowed_structured_uncertainty_categories_stay_held(evidence, category):
    """Purpose: preserve genuine question categories. Parameters: fixture/category.
    Returns: None. Failures: grounded uncertainty is discarded or converted to PASS.
    """
    question = {**uncertainty(), "category": category}
    raw = answer("AUTHOR_REVIEW", uncertainties=[question])
    validated = review.validate_review(raw, review.build_payload(*evidence))
    result = review.legacy_result(validated, "fake-key", review.canonical_hash(evidence[0]))
    assert result["verdict"] == "REVIEW_REQUIRED"
    assert result["typed_review"]["uncertainties"] == [question]
    assert result["issues"] == [{"field": "new_sutra", "quote": FORMULA,
                                 "reason": question["question"], "severity": "uncertain"}]


@pytest.mark.parametrize("category", ["NEW_FORMULA", "NONVERBATIM", "PENDING_SCHOLAR_REVIEW", "UNKNOWN"])
def test_generic_uncertainty_categories_are_rejected(evidence, category):
    """Purpose: reject novelty as an uncertainty category. Parameters: invalid label.
    Returns: None. Failures: a generic caveat masquerades as scholarly uncertainty.
    """
    with pytest.raises(ValueError, match="not a concrete uncertainty"):
        review.validate_review(answer("AUTHOR_REVIEW", uncertainties=[{**uncertainty(), "category": category}]),
                               review.build_payload(*evidence))


def current_field(draft, path):
    """Purpose: resolve a published dot path independently. Parameters: draft/path.
    Returns: exact field value. Failures: nonexistent keys/indexes fail the test.
    """
    value = draft
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def test_v26_payload_exact_allowlist_and_no_evaluator_labels(evidence):
    """Purpose: freeze the opinion-blind v2.6 boundary. Parameters: fixture.
    Returns: None. Failures: extra keys/labels or attacker-supplied checks survive.
    """
    draft, sources, cards = deepcopy(evidence)
    for record in (draft, sources, cards[0], draft["comparative_mr"][0],
                   draft["references"][0], draft["examples"][0],
                   sources["references"][0], sources["examples"][0]):
        record.update(OPINIONS)
        record["unexpected_metadata"] = "NOT_EVIDENCE_DO_NOT_SEND"
    draft["00_review_checks"] = {"formula_word_count": 999, "expected": "FORGED_CHECK_DO_NOT_SEND"}
    draft["evidence_selection"] = {"catalog": {"FORGED_REF": "FORGED_SELECTION_DO_NOT_SEND"}}
    draft["decision_comparisons"] = {"entry-2": "FORGED_DECISION_DO_NOT_SEND"}
    payload = review.build_payload(draft, sources, cards)
    assert set(payload) == {"00_review_checks", "current_draft", "canonical_sources",
                            "comparison_chapters", "current_business_decision",
                            "classical_source_policy", "historical_formula_policy", "evidence_selection",
                            "decision_comparisons"}
    assert set(payload["current_draft"]) == set(evidence[0])
    assert set(payload["canonical_sources"]) == {"references", "examples"}
    assert payload["canonical_sources"] == evidence[1]
    assert payload["comparison_chapters"] == evidence[2]
    assert payload["current_draft"]["references"] == evidence[0]["references"]
    assert payload["current_draft"]["examples"] == evidence[0]["examples"]
    assert payload["current_draft"]["comparative_mr"] == evidence[0]["comparative_mr"]
    checks = payload["00_review_checks"]
    assert set(checks) == {"formula_word_count", "formula_character_count", "exposition_word_count",
                           "exact_formula_matches", "source_claim_pairs", "case_fact_pairs"}
    assert checks["formula_word_count"] == 4
    assert checks["exact_formula_matches"] == []
    encoded = json.dumps(payload, ensure_ascii=False)
    assert all(marker not in encoded for marker in OPINIONS.values())
    assert "NOT_EVIDENCE_DO_NOT_SEND" not in encoded
    assert "FORGED_CHECK_DO_NOT_SEND" not in encoded
    assert "FORGED_SELECTION_DO_NOT_SEND" not in encoded
    assert "FORGED_DECISION_DO_NOT_SEND" not in encoded
    assert payload["evidence_selection"]["comparisons"]


def test_computed_counts_strip_dandas_and_ignore_non_devanagari_tokens(evidence):
    """Purpose: supply reliable mechanical measurements. Parameters: fixture.
    Returns: None. Failures: enclosing marks or nonwords inflate the counts.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["new_sutra"] = "। " + FORMULA + " ॥"
    draft["exposition"].append("English 123 १२३ !!!")
    checks = review.build_payload(draft, sources, cards)["00_review_checks"]
    assert checks["formula_word_count"] == 4
    assert checks["formula_character_count"] == len(FORMULA)
    assert checks["exposition_word_count"] == 500


@pytest.mark.parametrize("count", [499, 500])
def test_exposition_count_and_mechanical_gate_share_threshold(evidence, count):
    """Purpose: distinguish the 499/500 boundary. Parameters: fixture/count.
    Returns: None. Failures: computed counts or blocker validation disagree.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["exposition"] = ["विचार " * count]
    payload = review.build_payload(draft, sources, cards)
    assert payload["00_review_checks"]["exposition_word_count"] == count
    blocker = issue("MECHANICAL", {"rule": "exposition_minimum"}, field="exposition.0", quote="विचार")
    raw = answer("REVISION_REQUIRED", issues=[blocker])
    if count == 499:
        assert review.validate_review(raw, payload) == raw
    else:
        with pytest.raises(ValueError, match="Mechanical objection contradicted"):
            review.validate_review(raw, payload)


def test_overlong_formula_does_not_invent_word_limit_defect(evidence):
    """Purpose: isolate character and word limits. Parameters: fixture.
    Returns: None. Failures: a three-word long formula becomes a word-limit defect.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["new_sutra"] = "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं कुर्यात्"
    payload = review.build_payload(draft, sources, cards)
    checks = payload["00_review_checks"]
    assert checks["formula_word_count"] == 3
    assert checks["formula_character_count"] == len(draft["new_sutra"]) > 32
    wrong = issue("MECHANICAL", {"rule": "word_limit"}, quote=draft["new_sutra"])
    with pytest.raises(ValueError, match="Mechanical objection contradicted"):
        review.validate_review(answer("REVISION_REQUIRED", issues=[wrong]), payload)
    correct = issue("MECHANICAL", {"rule": "character_limit"}, quote=draft["new_sutra"])
    raw = answer("REVISION_REQUIRED", issues=[correct])
    assert review.validate_review(raw, payload) == raw


def test_computed_exact_matches_only_include_actual_formula_matches(evidence):
    """Purpose: separate exact copying from thematic sameness. Parameters: fixture.
    Returns: None. Failures: decision similarity produces false exact matches.
    """
    draft, sources, cards = deepcopy(evidence)
    cards.extend([
        {**cards[0], "id": "exact-copy", "formula": "। " + FORMULA.replace(" ", "  ") + " ॥"},
        {**cards[0], "id": "same-action-different-formula", "formula": "प्रश्नेन विवेकः"},
    ])
    payload = review.build_payload(draft, sources, cards)
    assert payload["00_review_checks"]["exact_formula_matches"] == ["exact-copy"]
    rejected = answer("REVISION_REQUIRED", issues=[issue("EXACT_COPY", {"comparator_id": "exact-copy"})])
    assert review.validate_review(rejected, payload) == rejected


def test_claim_pairs_resolve_current_paths_and_match_sources_by_id(evidence):
    """Purpose: expose planted attribution claims beside canonical text. Parameters: fixture.
    Returns: None. Failures: index-based source matching or incorrect draft paths.
    """
    draft, sources, cards = deepcopy(evidence)
    sources["references"].insert(0, {"id": "S2", "title": "Other synthetic source",
        "original_text": "Preserve the decision record.", "meaning_mr": "निर्णयाची नोंद ठेवा."})
    draft["comparative_mr"] = [
        {"source_id": "S1", "explanation_mr": "The source orders product release within 24 hours."},
        {"source_id": "S2", "explanation_mr": "A modern application is to keep a decision log."},
    ]
    payload = review.build_payload(draft, sources, cards)
    pairs = payload["00_review_checks"]["source_claim_pairs"]
    assert len(pairs) == 2
    assert [p["field"] for p in pairs] == ["comparative_mr.0.explanation_mr", "comparative_mr.1.explanation_mr"]
    canonical = {source["id"]: source for source in sources["references"]}
    for pair in pairs:
        assert set(pair) == {"field", "current_claim", "source_id", "original_text", "canonical_meaning"}
        assert current_field(payload["current_draft"], pair["field"]) == pair["current_claim"]
        assert pair["original_text"] == canonical[pair["source_id"]]["original_text"]
        assert pair["canonical_meaning"] == canonical[pair["source_id"]]["meaning_mr"]
    assert "24 hours" in pairs[0]["current_claim"]
    assert "24 hours" not in pairs[0]["original_text"]
    blocker = issue("SOURCE_DISTORTION", {"source_id": "S1", "source_quote": pairs[0]["original_text"],
        "contradiction": "The canonical passage does not prescribe a 24-hour product release."},
        field=pairs[0]["field"], quote=pairs[0]["current_claim"])
    checks = [
        source_check("FALSE_ATTRIBUTION", claim=pairs[0]["current_claim"], application=""),
        source_check(field=pairs[1]["field"], source_id="S2", application=pairs[1]["current_claim"],
                     source_quote=pairs[1]["original_text"]),
    ]
    raw = answer("REVISION_REQUIRED", issues=[blocker], source_checks=checks)
    assert review.validate_review(raw, payload) == raw


def test_case_pairs_expose_mutation_and_keep_canonical_text(evidence):
    """Purpose: expose planted business-fact changes. Parameters: fixture.
    Returns: None. Failures: canonical facts are replaced or case IDs matched by index.
    """
    draft, sources, cards = deepcopy(evidence)
    other = {"case_id": "C2", "entity": "Other synthetic business", "text_mr": "संस्थेने पर्याय तपासले."}
    sources["examples"].insert(0, deepcopy(other))
    draft["examples"][0]["text_mr"] += " प्रत्येक ग्राहकाचे उत्पन्न दुप्पट झाले."
    draft["examples"].append(deepcopy(other))
    payload = review.build_payload(draft, sources, cards)
    pairs = payload["00_review_checks"]["case_fact_pairs"]
    assert len(pairs) == 2
    assert [p["field"] for p in pairs] == ["examples.0.text_mr", "examples.1.text_mr"]
    canonical = {case["case_id"]: case for case in sources["examples"]}
    for pair in pairs:
        assert set(pair) == {"field", "case_id", "current_text", "canonical_text", "changed_fields"}
        assert current_field(payload["current_draft"], pair["field"]) == pair["current_text"]
        assert pair["canonical_text"] == canonical[pair["case_id"]]["text_mr"]
    assert pairs[0]["changed_fields"] == ["text_mr"]
    assert pairs[1]["changed_fields"] == []
    assert pairs[0]["current_text"] != pairs[0]["canonical_text"]
    blocker = issue("CASE_FACT", {"case_id": "C1", "canonical_quote": pairs[0]["canonical_text"],
        "contradiction": "The canonical case does not say every customer's income doubled."},
        field=pairs[0]["field"], quote="प्रत्येक ग्राहकाचे उत्पन्न दुप्पट झाले.")
    raw = answer("REVISION_REQUIRED", issues=[blocker])
    assert review.validate_review(raw, payload) == raw


def test_claim_and_case_pairs_are_deep_copies(evidence):
    """Purpose: protect immutable packet and draft. Parameters: fixture.
    Returns: None. Failures: mutations of derived review aids alter source inputs.
    """
    original = deepcopy(evidence)
    payload = review.build_payload(*evidence)
    checks = payload["00_review_checks"]
    checks["source_claim_pairs"][0]["current_claim"] = "changed"
    checks["source_claim_pairs"][0]["original_text"] = "changed"
    checks["case_fact_pairs"][0]["canonical_text"] = "changed"
    checks["case_fact_pairs"][0]["changed_fields"].append("text_mr")
    assert evidence == original
    assert payload["current_draft"]["comparative_mr"] == original[0]["comparative_mr"]
    assert payload["canonical_sources"] == original[1]



def contrast_source_evidence(evidence, variant):
    """Purpose: build analogy/false/mixed contrast records. Parameters: variant.
    Returns: draft/sources/cards, check, blockers. Failures: unknown variant fails.
    These are synthetic classifications, not a test of a live model's judgment.
    """
    draft, sources, cards = deepcopy(evidence)
    original_claim = "The passage recommends asking questions before deciding."
    application = "As a modern business analogy, ask customers before testing a product."
    false_claim = "The passage orders every business to launch within 24 hours."
    disclaimer = "This is our modern business analogy, not an ancient operational rule."
    if variant == "analogy":
        text = original_claim + " " + application
        check = source_check(claim=original_claim, application=application)
        blockers = []
    elif variant in {"false", "mixed"}:
        text = false_claim if variant == "false" else false_claim + " " + disclaimer
        check = source_check("FALSE_ATTRIBUTION", claim=false_claim,
                             application="" if variant == "false" else disclaimer)
        blockers = [issue("SOURCE_DISTORTION", {"source_id": "S1",
            "source_quote": check["source_quote"],
            "contradiction": "The passage contains no mandatory 24-hour business launch rule."},
            field=check["field"], quote=false_claim)]
    else:
        raise AssertionError("Unknown synthetic contrast variant")
    draft["comparative_mr"][0]["explanation_mr"] = text
    return (draft, sources, cards), check, blockers


@pytest.mark.parametrize("variant", ["analogy", "false", "mixed"])
def test_source_contrast_triples_keep_analogy_distinct_from_false_claim(evidence, variant):
    """Purpose: preserve mixed false claims despite a disclaimer. Parameters: variant.
    Returns: None. Failures: false/mixed evidence is dropped or valid analogy held.
    """
    supplied, check, blockers = contrast_source_evidence(evidence, variant)
    raw = answer("REVISION_REQUIRED" if blockers else "READY", issues=blockers, source_checks=[check])
    validated = review.validate_review(raw, review.build_payload(*supplied))
    result = review.legacy_result(validated, "fake-key", review.canonical_hash(supplied[0]))
    assert result["verdict"] == ("PASS" if variant == "analogy" else "REVIEW_REQUIRED")
    assert result["typed_review"]["source_checks"] == [check]
    if variant == "mixed":
        assert check["application_quote"] and check["source_claim_quote"]
        assert result["issues"][0]["quote"] == check["source_claim_quote"]


@pytest.mark.parametrize("variant", ["false", "mixed"])
def test_false_or_mixed_source_classification_cannot_silently_pass(evidence, variant):
    """Purpose: require the false-claim blocker even with a disclaimer. Parameters: variant.
    Returns: None. Failures: false classification without a blocker becomes READY.
    """
    supplied, check, _ = contrast_source_evidence(evidence, variant)
    with pytest.raises(ValueError, match="matching source blocker"):
        review.validate_review(answer(source_checks=[check]), review.build_payload(*supplied))


@pytest.mark.parametrize("kind", ["FALSE_ATTRIBUTION", "DISTORTED_MEANING"])
@pytest.mark.parametrize("mismatch", ["quote", "field", "source_id"])
def test_false_source_check_requires_exact_matching_blocker(evidence, kind, mismatch):
    """Purpose: bind claim/blocker field, source and literal quote. Parameters: mismatch.
    Returns: None. Failures: a different grounded issue satisfies the false-claim check.
    """
    supplied, check, blockers = contrast_source_evidence(evidence, "mixed")
    draft, sources, _ = supplied
    check["classification"] = kind
    if mismatch == "quote":
        blockers[0]["quote"] = "launch within 24 hours"
    elif mismatch == "field":
        draft["exposition"].append(check["source_claim_quote"])
        blockers[0]["field"] = "exposition.1"
    else:
        sources["references"].append({**sources["references"][0], "id": "S2"})
        blockers[0]["evidence"]["source_id"] = "S2"
    with pytest.raises(ValueError, match="matching source blocker"):
        review.validate_review(answer("REVISION_REQUIRED", issues=blockers, source_checks=[check]),
                               review.build_payload(*supplied))


def test_distorted_source_meaning_with_matched_evidence_remains_blocked(evidence):
    """Purpose: preserve a grounded distortion rejection. Parameters: fixture.
    Returns: None. Failures: valid typed distortion is lost in source-check handling.
    """
    draft, sources, cards = deepcopy(evidence)
    text = "The passage says never ask questions before deciding."
    draft["comparative_mr"][0]["explanation_mr"] = text
    check = source_check("DISTORTED_MEANING", claim=text, application="")
    blocker = issue("SOURCE_DISTORTION", {"source_id": "S1", "source_quote": check["source_quote"],
        "contradiction": "The current attribution reverses the instruction to ask questions."},
        field=check["field"], quote=text)
    raw = answer("REVISION_REQUIRED", issues=[blocker], source_checks=[check])
    assert review.validate_review(raw, review.build_payload(draft, sources, cards)) == raw


@pytest.mark.parametrize("kind", ["SUPPORTED_ORIGINAL", "FALSE_ATTRIBUTION", "DISTORTED_MEANING"])
def test_original_or_false_source_check_requires_claim_quote(evidence, kind):
    """Purpose: require the specific attributed claim. Parameters: classification.
    Returns: None. Failures: empty source-claim evidence is allowed for these classes.
    """
    with pytest.raises(ValueError):
        review.validate_review(answer(source_checks=[source_check(kind, claim="")]),
                               review.build_payload(*evidence))


def test_supported_original_uses_literal_current_and_canonical_quotes(evidence):
    """Purpose: allow a supported original-source statement. Parameters: fixture.
    Returns: None. Failures: literal supported evidence is unnecessarily blocked.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["comparative_mr"][0]["explanation_mr"] = sources["references"][0]["original_text"]
    check = source_check("SUPPORTED_ORIGINAL", claim=draft["comparative_mr"][0]["explanation_mr"], application="")
    raw = answer(source_checks=[check])
    assert review.validate_review(raw, review.build_payload(draft, sources, cards)) == raw


def test_qualified_analogy_requires_literal_application_quote(evidence):
    """Purpose: require identifiable business application. Parameters: fixture.
    Returns: None. Failures: an empty application quote justifies analogy status.
    """
    with pytest.raises(ValueError):
        review.validate_review(answer(source_checks=[source_check(application="")]),
                               review.build_payload(*evidence))


@pytest.mark.parametrize("field", ["field", "source_id", "source_claim_quote", "application_quote",
                                    "source_quote", "classification", "reason"])
def test_source_checks_require_exactly_seven_fields(evidence, field):
    """Purpose: enforce the seven-field response schema. Parameters: missing key.
    Returns: None. Failures: omitted evidence key is silently accepted.
    """
    check = source_check()
    check.pop(field)
    with pytest.raises(ValueError, match="exactly seven"):
        review.validate_review(answer(source_checks=[check]), review.build_payload(*evidence))


def test_source_check_extra_keys_are_rejected(evidence):
    """Purpose: reject extra verdict/editorial fields. Parameters: fixture.
    Returns: None. Failures: source checks can carry undeclared fields or edits.
    """
    check = {**source_check(), "replacement_text": "rewritten prose"}
    with pytest.raises(ValueError, match="exactly seven"):
        review.validate_review(answer(source_checks=[check]), review.build_payload(*evidence))


@pytest.mark.parametrize("kind", ["ANALOGY", "UNKNOWN", "PASS", "EDITORIAL_PREFERENCE"])
def test_unsupported_source_classifications_are_invalid(evidence, kind):
    """Purpose: reject invented classification labels. Parameters: invalid label.
    Returns: None. Failures: unsupported category reaches a valid review verdict.
    """
    with pytest.raises(ValueError, match="Unknown source classification"):
        review.validate_review(answer(source_checks=[source_check(kind)]), review.build_payload(*evidence))


@pytest.mark.parametrize("changes", [
    {"field": "comparative_mr.9.explanation_mr"}, {"source_id": "S2"},
    {"source_claim_quote": "absent historical claim"}, {"application_quote": "absent application"},
    {"source_quote": "absent canonical passage"}, {"source_quote": ""},
    {"application_quote": None}, {"source_claim_quote": None}, {"reason": ""},
])
def test_source_checks_reject_nonliteral_or_wrong_identity_evidence(evidence, changes):
    """Purpose: ground every source check in current/canonical text. Parameters: mutation.
    Returns: None. Failures: absent quotes, wrong paths or IDs pass validation.
    """
    with pytest.raises(ValueError):
        review.validate_review(answer(source_checks=[{**source_check(), **changes}]),
                               review.build_payload(*evidence))


@pytest.mark.parametrize("coverage", ["missing", "extra", "duplicate", "not_list"])
def test_source_checks_cover_every_comparison_exactly_once(evidence, coverage):
    """Purpose: require exhaustive unique comparison coverage. Parameters: bad coverage.
    Returns: None. Failures: missing, duplicated, extra or malformed check set passes.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["comparative_mr"].append(deepcopy(draft["comparative_mr"][0]))
    checks = [source_check(), source_check(field="comparative_mr.1.explanation_mr")]
    if coverage == "missing": checks.pop()
    elif coverage == "extra": checks.append(source_check(field="comparative_mr.2.explanation_mr"))
    elif coverage == "duplicate": checks[1] = deepcopy(checks[0])
    else: checks = {"not": "a list"}
    with pytest.raises(ValueError):
        review.validate_review(answer(source_checks=checks), review.build_payload(draft, sources, cards))


def test_repeated_source_id_still_requires_separate_comparison_checks(evidence):
    """Purpose: key coverage by field rather than source alone. Parameters: fixture.
    Returns: None. Failures: two comparisons to one source collapse into one check.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["comparative_mr"].append(deepcopy(draft["comparative_mr"][0]))
    checks = [source_check(field="comparative_mr.1.explanation_mr"), source_check()]
    raw = answer(source_checks=checks)
    assert review.validate_review(raw, review.build_payload(draft, sources, cards)) == raw


def test_no_comparisons_requires_empty_source_checks(evidence):
    """Purpose: support the explicit empty-comparison case. Parameters: fixture.
    Returns: None. Failures: empty coverage is rejected or invented checks accepted.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["comparative_mr"] = []
    payload = review.build_payload(draft, sources, cards)
    raw = answer(source_checks=[])
    assert review.validate_review(raw, payload) == raw
    with pytest.raises(ValueError):
        review.validate_review(answer(), payload)


@pytest.mark.parametrize("category", ["SOURCE_EDITION", "CONFLICTING_EVIDENCE"])
def test_unresolved_source_requires_matching_grounded_uncertainty(evidence, category):
    """Purpose: preserve real source uncertainty without a rewrite. Parameters: category.
    Returns: None. Failures: unresolved source loses its anchored scholarly question.
    """
    check = source_check("UNRESOLVED_SOURCE")
    question = {"category": category, "field": check["field"], "quote": check["application_quote"],
                "question": "Which supplied edition establishes the intended sense of this comparison?"}
    raw = answer("AUTHOR_REVIEW", uncertainties=[question], source_checks=[check])
    assert review.validate_review(raw, review.build_payload(*evidence)) == raw


@pytest.mark.parametrize("mismatch", ["missing", "wrong_field", "lexical_only"])
def test_unresolved_source_cannot_use_missing_or_unrelated_uncertainty(evidence, mismatch):
    """Purpose: bind unresolved status to a source question at the same field.
    Parameters: mismatch and fixture. Returns: None. Failures: unrelated hold suffices.
    """
    check = source_check("UNRESOLVED_SOURCE")
    questions = [] if mismatch == "missing" else [uncertainty()]
    if mismatch == "wrong_field": questions[0]["category"] = "SOURCE_EDITION"
    if mismatch == "lexical_only":
        questions[0].update(field=check["field"], quote=check["application_quote"])
    with pytest.raises(ValueError, match="concrete source uncertainty"):
        review.validate_review(answer("AUTHOR_REVIEW" if questions else "READY",
                                      uncertainties=questions, source_checks=[check]), review.build_payload(*evidence))


@pytest.mark.parametrize("category", ["SOURCE_EDITION", "CONFLICTING_EVIDENCE"])
def test_qualified_analogy_cannot_also_have_generic_source_hold(evidence, category):
    """Purpose: reject mutually contradictory resolved/held source judgments.
    Parameters: uncertainty category. Returns: None. Failures: a resolved analogy is held as unresolved.
    """
    check = source_check()
    question = {"category": category, "field": check["field"], "quote": check["application_quote"],
                "question": "Must this modern analogy occur literally in the classical passage?"}
    with pytest.raises(ValueError, match="contradicts resolved source"):
        review.validate_review(answer("AUTHOR_REVIEW", uncertainties=[question]), review.build_payload(*evidence))


def test_qualified_analogy_allows_independent_lexical_uncertainty(evidence):
    """Purpose: retain unrelated lexical questions. Parameters: fixture.
    Returns: None. Failures: analogy status automatically clears lexical uncertainty.
    """
    check = source_check()
    question = {**uncertainty(), "field": check["field"], "quote": check["application_quote"],
                "question": "Which sense of उपयोग is intended in this current sentence?"}
    raw = answer("AUTHOR_REVIEW", uncertainties=[question])
    assert review.validate_review(raw, review.build_payload(*evidence)) == raw


def test_qualified_analogy_does_not_force_pass_over_other_blocker(evidence):
    """Purpose: preserve independently grounded defects. Parameters: fixture.
    Returns: None. Failures: accepted analogy overrides an unrelated grammar blocker.
    """
    blocker = issue("GRAMMAR", {"rule": "Synthetic agreement rule", "explanation": "Synthetic application of the rule."})
    raw = answer("REVISION_REQUIRED", issues=[blocker])
    assert review.validate_review(raw, review.build_payload(*evidence)) == raw


def test_mixed_disclaimer_cannot_relabel_matching_false_blocker_as_analogy(evidence):
    """Purpose: reject inconsistent laundering of a mixed false attribution.
    Parameters: fixture. Returns: None. Failures: disclaimer suppresses the matched blocker.
    """
    supplied, check, blockers = contrast_source_evidence(evidence, "mixed")
    check["classification"] = "QUALIFIED_ANALOGY"
    with pytest.raises(ValueError, match="blocker contradicts source classification"):
        review.validate_review(answer("REVISION_REQUIRED", issues=blockers, source_checks=[check]),
                               review.build_payload(*supplied))


def test_source_checks_raw_response_replays_without_extra_callback(tmp_path, evidence):
    """Purpose: preserve complete fifth-field evidence in paid-cache replay.
    Parameters: tmp_path/fixture. Returns: None. Failures: checks lost, mutated or paid again.
    """
    supplied, check, blockers = contrast_source_evidence(evidence, "mixed")
    # The reference wire puts the explanation in reason, not a redundant evidence key.
    blockers[0]["evidence"].pop("contradiction")
    raw = answer("REVISION_REQUIRED", issues=blockers, source_checks=[check])
    callback = reference_callback(raw)
    path = tmp_path / "review.sqlite3"
    first = review.IndependentReviewer(path, callback).review(*supplied)
    persisted = rows(path)
    assert len(persisted) == 1 and persisted[0][1] == "COMPLETE"
    assert json.loads(persisted[0][3]) == callback.wire_responses[0]
    assert first["evidence_selections"]
    assert json.loads(persisted[0][3]) != raw
    first["typed_review"]["source_checks"][0]["reason"] = "caller mutation"
    no_call = Mock(side_effect=AssertionError("Replay must not dispatch"))
    replay = review.IndependentReviewer(path, no_call).review(*supplied)
    assert replay["typed_review"] == raw
    assert replay["verdict"] == "REVIEW_REQUIRED"
    callback.assert_called_once()
    no_call.assert_not_called()


def test_invalid_source_check_response_is_saved_failed_without_retry(tmp_path, evidence):
    """Purpose: persist malformed source checks without writer/review retries.
    Parameters: tmp_path/fixture. Returns: None. Failures: missing coverage is retried or passed.
    """
    raw = answer(source_checks=[])
    callback = reference_callback(raw)
    path = tmp_path / "review.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*evidence)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*evidence)
    persisted = rows(path)
    assert len(persisted) == 1 and persisted[0][1] == "FAILED"
    assert json.loads(persisted[0][3]) == callback.wire_responses[0]
    callback.assert_called_once()


def test_legacy_four_field_response_cannot_skip_source_checks(evidence):
    """Purpose: prevent replaying an obsolete response shape as v2.3.
    Parameters: fixture. Returns: None. Failures: omitted source_checks silently passes.
    """
    raw = answer()
    del raw["source_checks"]
    with pytest.raises(ValueError, match="exactly five"):
        review.validate_review(raw, review.build_payload(*evidence))



@pytest.mark.parametrize("ancestor", ["comparative_mr", "comparative_mr.0"])
def test_source_blocker_cannot_bypass_classification_with_ancestor_field(evidence, ancestor):
    """Purpose: reject ancestor-path source blockers despite literal nested quotes.
    Parameters: fixture and ancestor path. Returns: None. Failures: a resolved
    analogy is blocked through a parent object outside exact source-check coverage.
    """
    check = source_check()
    blocker = issue("SOURCE_DISTORTION", {"source_id": "S1", "source_quote": check["source_quote"],
        "contradiction": "Synthetic objection to this comparison."},
        field=ancestor, quote=check["application_quote"])
    # The quote exists under this ancestor, so literal-quote validation alone is insufficient.
    assert check["application_quote"] in json.dumps(current_field(evidence[0], ancestor), ensure_ascii=False)
    raw = answer("REVISION_REQUIRED", issues=[blocker], source_checks=[check])
    with pytest.raises(ValueError, match="Source blocker must name the exact comparison field"):
        review.validate_review(raw, review.build_payload(*evidence))


@pytest.mark.parametrize("ancestor", ["comparative_mr", "comparative_mr.0"])
@pytest.mark.parametrize("category", ["SOURCE_EDITION", "CONFLICTING_EVIDENCE"])
def test_source_uncertainty_cannot_bypass_classification_with_ancestor_field(evidence, ancestor, category):
    """Purpose: reject unresolved-source holds on parent comparison objects.
    Parameters: ancestor and allowed uncertainty category. Returns: None. Failures:
    an exact comparison's resolved classification is bypassed via its ancestor.
    """
    check = source_check()
    question = {"category": category, "field": ancestor, "quote": check["application_quote"],
                "question": "Which source edition supports the sense used in this comparison?"}
    assert question["quote"] in json.dumps(current_field(evidence[0], ancestor), ensure_ascii=False)
    raw = answer("AUTHOR_REVIEW", uncertainties=[question], source_checks=[check])
    with pytest.raises(ValueError, match="Source uncertainty must name the exact comparison field"):
        review.validate_review(raw, review.build_payload(*evidence))


@pytest.mark.parametrize("kind", ["FALSE_ATTRIBUTION", "DISTORTED_MEANING"])
@pytest.mark.parametrize("wrong_first", [False, True])
def test_every_comparison_blocker_must_match_source_even_with_one_good_blocker(evidence, kind, wrong_first):
    """Purpose: reject extra wrong-source blockers hidden beside a valid match.
    Parameters: classification/order. Returns: None. Failures: finding one good
    blocker permits another blocker to cite a different supplied canonical source.
    """
    supplied, check, blockers = contrast_source_evidence(evidence, "mixed")
    check["classification"] = kind
    supplied[1]["references"].append({**supplied[1]["references"][0], "id": "S2"})
    wrong = deepcopy(blockers[0])
    wrong["evidence"]["source_id"] = "S2"
    blockers.insert(0 if wrong_first else len(blockers), wrong)
    # S2 is real and its canonical quote is literal; only the comparison identity is wrong.
    assert len(blockers) == 2
    raw = answer("REVISION_REQUIRED", issues=blockers, source_checks=[check])
    with pytest.raises(ValueError, match="Source blocker cites a different comparison source"):
        review.validate_review(raw, review.build_payload(*supplied))



@pytest.mark.parametrize("category", ["SOURCE_DISTORTION", "CASE_FACT"])
def test_source_and_case_blockers_need_no_redundant_contradiction(evidence, category):
    """Purpose: accept literal evidence with the explanation in mandatory reason.
    Parameters: evidence/category. Returns: None. Failures: a redundant evidence
    explanation is required or the substantive reason/evidence is discarded.
    """
    if category == "SOURCE_DISTORTION":
        supplied, check, blockers = contrast_source_evidence(evidence, "false")
        blocker = blockers[0]
        blocker["evidence"].pop("contradiction")
        blocker["reason"] = "The supplied passage does not prescribe a 24-hour product-launch rule."
        raw = answer("REVISION_REQUIRED", issues=[blocker], source_checks=[check])
    else:
        supplied = deepcopy(evidence)
        supplied[0]["examples"][0]["text_mr"] += " सर्व ग्राहकांचे उत्पन्न दुप्पट झाले."
        blocker = issue("CASE_FACT", {"case_id": "C1", "canonical_quote": supplied[1]["examples"][0]["text_mr"]},
                        field="examples.0.text_mr", quote="सर्व ग्राहकांचे उत्पन्न दुप्पट झाले.")
        blocker["reason"] = "The supplied case does not claim every customer's income doubled."
        raw = answer("REVISION_REQUIRED", issues=[blocker])
    assert "contradiction" not in blocker["evidence"]
    assert len(blocker["evidence"]) == 2
    assert review.validate_review(raw, review.build_payload(*supplied)) == raw


@pytest.mark.parametrize("category", ["SOURCE_DISTORTION", "CASE_FACT"])
@pytest.mark.parametrize("reason", [None, "", " "])
def test_source_and_case_blockers_still_require_explanatory_reason(evidence, category, reason):
    """Purpose: preserve nonempty reasons after removing redundant evidence text.
    Parameters: category/reason. Returns: None. Failures: minimally cited but
    unexplained complaints are accepted as substantiated defects.
    """
    proof = ({"source_id": "S1", "source_quote": evidence[1]["references"][0]["original_text"]}
             if category == "SOURCE_DISTORTION" else
             {"case_id": "C1", "canonical_quote": evidence[1]["examples"][0]["text_mr"]})
    blocker = issue(category, proof)
    if reason is None:
        blocker.pop("reason")
    else:
        blocker["reason"] = reason
    with pytest.raises(ValueError, match="evidence missing"):
        review.validate_review(answer("REVISION_REQUIRED", issues=[blocker]), review.build_payload(*evidence))


@pytest.mark.parametrize("rule", ["word_limit", "character_limit", "exposition_minimum"])
@pytest.mark.parametrize("disposition", ["READY", "AUTHOR_REVIEW", "unrelated_defect"])
def test_objective_limit_omissions_are_invalid_for_every_disposition(evidence, rule, disposition):
    """Purpose: prevent known objective failures from being silently omitted.
    Parameters: failed rule/disposition. Returns: None. Failures: READY, uncertainty
    or another blocker excuses missing a required mechanical-limit finding.
    """
    draft, sources, cards = deepcopy(evidence)
    if rule == "word_limit":
        draft["new_sutra"] = "एकं द्वे त्रीणि चत्वारि पञ्च"
    elif rule == "character_limit":
        draft["new_sutra"] = "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं कुर्यात्"
    else:
        draft["exposition"] = ["विचार " * 499]
    if disposition == "unrelated_defect":
        blocker = issue("GRAMMAR", {"rule": "Synthetic grammatical rule", "explanation": "Synthetic application."},
                        quote=draft["new_sutra"])
        raw = answer("REVISION_REQUIRED", issues=[blocker])
    elif disposition == "AUTHOR_REVIEW":
        raw = answer("AUTHOR_REVIEW", uncertainties=[uncertainty(quote=draft["new_sutra"])])
    else:
        raw = answer()
    with pytest.raises(ValueError, match="omitted an objective limit violation"):
        review.validate_review(raw, review.build_payload(draft, sources, cards))


@pytest.mark.parametrize("omitted", [None, "word_limit", "character_limit", "exposition_minimum"])
def test_every_actual_mechanical_violation_must_be_reported(evidence, omitted):
    """Purpose: enforce complete objective-rule coverage. Parameters: omitted rule.
    Returns: None. Failures: only some true limits suffice, or complete evidence fails.
    """
    draft, sources, cards = deepcopy(evidence)
    draft["new_sutra"] = "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं विवेकं प्रमाणं कुर्यात्"
    draft["exposition"] = ["विचार " * 499]
    blockers = [issue("MECHANICAL", {"rule": rule},
                      field="exposition.0" if rule == "exposition_minimum" else "new_sutra",
                      quote="विचार" if rule == "exposition_minimum" else draft["new_sutra"])
                for rule in ("word_limit", "character_limit", "exposition_minimum") if rule != omitted]
    raw = answer("REVISION_REQUIRED", issues=blockers)
    payload = review.build_payload(draft, sources, cards)
    if omitted is None:
        assert review.validate_review(raw, payload) == raw
    else:
        with pytest.raises(ValueError, match="omitted an objective limit violation"):
            review.validate_review(raw, payload)


@pytest.mark.parametrize("disposition", ["READY", "AUTHOR_REVIEW", "DUPLICATE_DECISION"])
def test_actual_exact_copy_cannot_be_omitted_or_relabelled(evidence, disposition):
    """Purpose: require explicit exact-copy findings. Parameters: attempted disposition.
    Returns: None. Failures: thematic-duplicate or uncertain labels hide literal copying.
    """
    draft, sources, cards = deepcopy(evidence)
    cards[0]["formula"] = FORMULA
    if disposition == "DUPLICATE_DECISION":
        raw = answer("REVISION_REQUIRED", issues=[issue("DUPLICATE_DECISION", {
            "comparator_id": cards[0]["id"], "same_decision": "Same decision", "same_action": "Same action"})])
    elif disposition == "AUTHOR_REVIEW":
        raw = answer("AUTHOR_REVIEW", uncertainties=[uncertainty()])
    else:
        raw = answer()
    with pytest.raises(ValueError, match="omitted an exact formula copy"):
        review.validate_review(raw, review.build_payload(draft, sources, cards))


@pytest.mark.parametrize("complete", [False, True])
def test_every_matching_comparator_requires_its_own_exact_copy_issue(evidence, complete):
    """Purpose: cover all real exact matches. Parameters: completeness flag.
    Returns: None. Failures: one comparator finding hides another actual copy.
    """
    draft, sources, cards = deepcopy(evidence)
    cards[0]["formula"] = FORMULA
    cards.append({**cards[0], "id": "another-copy", "formula": "। " + FORMULA + " ॥"})
    raw = answer("REVISION_REQUIRED", issues=[issue("EXACT_COPY", {"comparator_id": card["id"]})
                 for card in (cards if complete else cards[:1])])
    payload = review.build_payload(draft, sources, cards)
    if complete:
        assert review.validate_review(raw, payload) == raw
    else:
        with pytest.raises(ValueError, match="omitted an exact formula copy"):
            review.validate_review(raw, payload)


@pytest.mark.parametrize("violation", ["count", "copy"])
def test_objective_omission_persists_failed_without_retry_or_writer(tmp_path, evidence, monkeypatch, violation):
    """Purpose: keep omitted objective defects terminal. Parameters: defect and fixtures.
    Returns: None. Failures: invalid READY is silently repaired, retried or passed.
    """
    supplied = deepcopy(evidence)
    if violation == "count":
        supplied[0]["exposition"] = ["विचार " * 499]
    else:
        supplied[2][0]["formula"] = FORMULA
    writer = Mock(side_effect=AssertionError("Invalid review cannot authorize a rewrite"))
    monkeypatch.setattr(ResearchCouncil, "_compose", writer)
    callback = reference_callback(answer())
    path = tmp_path / "review.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized"):
        review.IndependentReviewer(path, callback).review(*supplied)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*supplied)
    assert rows(path)[0][1] == "FAILED"
    callback.assert_called_once()
    writer.assert_not_called()



def formula_alias_case(evidence, kind="EXACT_COPY"):
    """Purpose: construct a narrow objective formula-alias response. Parameters: kind.
    Returns: synthetic inputs/raw response. Failures: unsupported fixture kind fails.
    """
    supplied = deepcopy(evidence)
    if kind == "EXACT_COPY":
        supplied[2][0]["formula"] = supplied[0]["new_sutra"]
        proof, category = {"comparator_id": supplied[2][0]["id"]}, "EXACT_COPY"
    elif kind in {"word_limit", "character_limit"}:
        supplied[0]["new_sutra"] = ("एकं द्वे त्रीणि चत्वारि पञ्च" if kind == "word_limit" else
                                     "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं कुर्यात्")
        proof, category = {"rule": kind}, "MECHANICAL"
    else:
        raise AssertionError("Unknown synthetic objective alias kind")
    raw = answer("REVISION_REQUIRED", issues=[issue(category, proof, field="formula", quote=supplied[0]["new_sutra"])])
    return supplied, raw


def seed_failed_formula_alias(path, supplied, raw, *, state="FAILED",
                              error="ValueError: Invalid review: unknown current field formula"):
    """Purpose: simulate a retained pre-normalizer failed row in a temporary cache.
    Parameters: path, inputs, raw response, state/error. Returns: exact request key.
    Failures: SQL errors; creates no provider calls and never touches the live cache.
    """
    review.IndependentReviewer(path, Mock(side_effect=AssertionError("Seeding cannot dispatch")))
    payload = review.build_payload(*supplied)
    prompt = review.CONTRACT + "\nEVIDENCE\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    request = {"contract_hash": review.contract_hash(), "payload": payload, "prompt": prompt, "system": review.SYSTEM}
    key = review.canonical_hash(request)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO independent_reviews_v2 VALUES (?,?,?,?,?)",
                   (key, state, json.dumps(request, ensure_ascii=False), json.dumps(raw, ensure_ascii=False), error))
    return key


@pytest.mark.parametrize("kind", ["EXACT_COPY", "word_limit", "character_limit"])
def test_full_formula_alias_normalizes_only_proven_objective_fields(evidence, kind):
    """Purpose: normalize the full literal formula for approved objective categories.
    Parameters: fixture/kind. Returns: None. Failures: input edits, lost rejection,
    missing normalization evidence or bypassed objective validation.
    """
    supplied, raw = formula_alias_case(evidence, kind)
    original = deepcopy(raw)
    payload = review.build_payload(*supplied)
    normalized, notes = review.canonicalize_review_fields(raw, payload)
    assert raw == original
    assert notes == [{"path": "blocking_issues.0.field", "from": "formula", "to": "new_sutra"}]
    assert normalized["blocking_issues"][0]["field"] == "new_sutra"
    assert normalized["outcome"] == "REVISION_REQUIRED"
    assert review.validate_review(normalized, payload) == normalized


@pytest.mark.parametrize("quote", ["विमतं", FORMULA + "।", " " + FORMULA])
def test_formula_alias_rejects_partial_or_nonexact_entire_quote(evidence, quote):
    """Purpose: prohibit field guessing from approximate formula evidence.
    Parameters: altered quote. Returns: None. Failures: partial/trimmed text is aliased.
    """
    supplied, raw = formula_alias_case(evidence)
    raw["blocking_issues"][0]["quote"] = quote
    normalized, notes = review.canonicalize_review_fields(raw, review.build_payload(*supplied))
    assert notes == [] and normalized == raw
    with pytest.raises(ValueError):
        review.validate_review(normalized, review.build_payload(*supplied))


@pytest.mark.parametrize("kind", ["GRAMMAR", "exposition_minimum"])
def test_formula_alias_does_not_normalize_grammar_or_exposition(evidence, kind):
    """Purpose: retain the narrow category/rule boundary. Parameters: unsupported kind.
    Returns: None. Failures: grammar or exposition issues get guessed formula fields.
    """
    proof = {"rule": "agreement", "explanation": "Synthetic rule application"} if kind == "GRAMMAR" else {"rule": kind}
    raw = answer("REVISION_REQUIRED", issues=[issue("GRAMMAR" if kind == "GRAMMAR" else "MECHANICAL",
                                                   proof, field="formula")])
    payload = review.build_payload(*evidence)
    normalized, notes = review.canonicalize_review_fields(raw, payload)
    assert notes == [] and normalized == raw
    with pytest.raises(ValueError):
        review.validate_review(normalized, payload)


@pytest.mark.parametrize("comparator", ["missing", "different-formula"])
def test_formula_alias_still_rejects_wrong_copy_comparator(evidence, comparator):
    """Purpose: prevent aliasing from certifying a false exact-copy allegation.
    Parameters: comparator mismatch. Returns: None. Failures: wrong comparator passes.
    """
    supplied, raw = formula_alias_case(evidence)
    if comparator == "different-formula":
        supplied[2].append({**supplied[2][0], "id": comparator, "formula": "प्रश्नेन विवेकः"})
    raw["blocking_issues"][0]["evidence"]["comparator_id"] = comparator
    payload = review.build_payload(*supplied)
    normalized, notes = review.canonicalize_review_fields(raw, payload)
    assert notes
    with pytest.raises(ValueError):
        review.validate_review(normalized, payload)


@pytest.mark.parametrize("rule", ["word_limit", "character_limit"])
def test_mechanical_formula_alias_still_checks_actual_predicate(evidence, rule):
    """Purpose: reject false mechanical claims after aliasing. Parameters: rule.
    Returns: None. Failures: alias normalization turns an invalid objection valid.
    """
    payload = review.build_payload(*evidence)
    raw = answer("REVISION_REQUIRED", issues=[issue("MECHANICAL", {"rule": rule}, field="formula")])
    normalized, notes = review.canonicalize_review_fields(raw, payload)
    assert notes
    with pytest.raises(ValueError, match="Mechanical objection contradicted"):
        review.validate_review(normalized, payload)


@pytest.mark.parametrize("field", ["formula", "new_sutra"])
def test_v26_rejects_legacy_quote_wire_without_alias_fallback(tmp_path, evidence, field):
    """Purpose: reject even an objectively correct legacy quote-format response.
    Parameters: legacy alias or canonical field. Returns: None. Failures: live quote
    fallback, normalization, missing raw evidence or an automatic paid retry.
    """
    supplied, raw = formula_alias_case(evidence)
    raw["blocking_issues"][0]["field"] = field
    raw["decision_checks"] = {supplied[2][0]["id"]: "EXACT_COPY"}
    callback = Mock(return_value=deepcopy(raw))
    path = tmp_path / "alias.sqlite3"
    with pytest.raises(RuntimeError, match="no composition rewrite authorized") as failure:
        review.IndependentReviewer(path, callback).review(*supplied)
    assert isinstance(failure.value.__cause__, ValueError)
    assert "Reference record" in str(failure.value.__cause__)
    assert rows(path)[0][1] == "FAILED"
    assert json.loads(rows(path)[0][3]) == raw
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, callback).review(*supplied)
    callback.assert_called_once()


def test_legacy_recovery_preserves_raw_but_cannot_bypass_v25_failed_cache(tmp_path, evidence):
    """Purpose: test offline legacy recovery without a v2.5 production bypass.
    Parameters: fixtures. Returns: None. Failures: paid replay, raw/state change,
    repeated recovery records or reopening a terminal production failure.
    """
    supplied, raw = formula_alias_case(evidence)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw)
    before = rows(path)
    no_call = Mock(side_effect=AssertionError("Recovery/replay must never dispatch"))
    reviewer = review.IndependentReviewer(path, no_call)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        reviewer.review(*supplied)
    record = review.recover_formula_field_alias(path, key)
    assert record["provider_calls"] == 0 and record["review_key"] == key
    assert record["raw_response_sha256"] == review.canonical_hash(raw)
    assert rows(path) == before
    assert review.recover_formula_field_alias(path, key) == record
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_alias_recoveries").fetchone()[0] == 1
    normalized, notes = review.canonicalize_review_fields(raw, review.build_payload(*supplied))
    assert review.validate_review(normalized, review.build_payload(*supplied))["outcome"] == "REVISION_REQUIRED"
    assert notes == record["normalizations"]
    with pytest.raises(RuntimeError, match="no automatic retry"):
        reviewer.review(*supplied)
    assert rows(path) == before
    no_call.assert_not_called()


@pytest.mark.parametrize("state,error", [
    ("COMPLETE", "ValueError: Invalid review: unknown current field formula"),
    ("RUNNING", "ValueError: Invalid review: unknown current field formula"),
    ("FAILED", "ValueError: Invalid review: unknown current field other"),
    ("FAILED", "TimeoutError: synthetic provider timeout"),
])
def test_alias_recovery_rejects_unrelated_states_or_errors(tmp_path, evidence, state, error):
    """Purpose: restrict recovery to the diagnosed FAILED row. Parameters: state/error.
    Returns: None. Failures: other states/provider/schema failures are reauthorized.
    """
    supplied, raw = formula_alias_case(evidence)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw, state=state, error=error)
    before = rows(path)
    with pytest.raises(ValueError, match="Only the diagnosed"):
        review.recover_formula_field_alias(path, key)
    assert rows(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_alias_recoveries").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["word_limit", "character_limit"])
def test_explicit_failed_recovery_does_not_expand_to_mechanical_aliases(tmp_path, evidence, kind):
    """Purpose: keep historical recovery EXACT_COPY-only. Parameters: mechanical rule.
    Returns: None. Failures: otherwise valid new-call normalization broadens recovery.
    """
    supplied, raw = formula_alias_case(evidence, kind)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw)
    before = rows(path)
    with pytest.raises(ValueError, match="cannot change a rejection"):
        review.recover_formula_field_alias(path, key)
    assert rows(path) == before


@pytest.mark.parametrize("change", ["request", "contract", "raw_ready"])
def test_alias_recovery_rejects_stale_request_contract_or_acceptance(tmp_path, evidence, monkeypatch, change):
    """Purpose: bind recovery to original request/current contract and rejection.
    Parameters: tampering kind. Returns: None. Failures: stale or accepting recovery succeeds.
    """
    supplied, raw = formula_alias_case(evidence)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw)
    if change == "contract":
        monkeypatch.setattr(review, "CONTRACT", review.CONTRACT + "\nchanged-contract")
    else:
        with sqlite3.connect(path) as db:
            if change == "request":
                request = json.loads(db.execute("SELECT request_json FROM independent_reviews_v2").fetchone()[0])
                request["prompt"] += "changed"
                db.execute("UPDATE independent_reviews_v2 SET request_json=?", (json.dumps(request),))
            else:
                db.execute("UPDATE independent_reviews_v2 SET response_json=?", (json.dumps(answer()),))
    with pytest.raises(ValueError):
        review.recover_formula_field_alias(path, key)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM independent_review_alias_recoveries").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["kind", "review_key", "normalizations", "raw_response_sha256",
                                     "normalized_response_sha256", "retained_raw"])
def test_v25_failed_cache_ignores_even_tampered_legacy_recovery(tmp_path, evidence, change):
    """Purpose: keep FAILED terminal regardless of legacy recovery contents. Parameters: tampering.
    Returns: None. Failures: recovery metadata reopens a failed row or dispatches a retry.
    """
    supplied, raw = formula_alias_case(evidence)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw)
    record = review.recover_formula_field_alias(path, key)
    with sqlite3.connect(path) as db:
        if change == "retained_raw":
            altered = deepcopy(raw)
            altered["blocking_issues"][0]["reason"] += " changed"
            db.execute("UPDATE independent_reviews_v2 SET response_json=?", (json.dumps(altered),))
        else:
            record[change] = [] if change == "normalizations" else "tampered"
            db.execute("UPDATE independent_review_alias_recoveries SET record_json=?", (json.dumps(record),))
    no_call = Mock(side_effect=AssertionError("Tampered recovery cannot dispatch"))
    with pytest.raises(RuntimeError, match="no automatic retry"):
        review.IndependentReviewer(path, no_call).review(*supplied)
    no_call.assert_not_called()


def test_alias_recovery_record_is_immutable(tmp_path, evidence):
    """Purpose: refuse replacing a conflicting existing recovery record.
    Parameters: fixtures. Returns: None. Failures: a second authorization overwrites audit.
    """
    supplied, raw = formula_alias_case(evidence)
    path = tmp_path / "alias.sqlite3"
    key = seed_failed_formula_alias(path, supplied, raw)
    record = review.recover_formula_field_alias(path, key)
    record["kind"] = "conflicting-recovery"
    encoded = json.dumps(record)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE independent_review_alias_recoveries SET record_json=?", (encoded,))
    with pytest.raises(ValueError, match="different alias recovery already exists"):
        review.recover_formula_field_alias(path, key)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT record_json FROM independent_review_alias_recoveries").fetchone()[0] == encoded
