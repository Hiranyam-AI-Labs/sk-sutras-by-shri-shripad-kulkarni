"""Prove editorial overlays cannot silently replace protected content or evidence."""

from copy import deepcopy
import pytest
from scripts.export_research_book import (
    apply_editorial_corrections, select_reviewed_draft, review_selection_evidence,
)
from src.orchestration.independent_review import canonical_hash


def test_literal_overlay_leaves_provider_draft_and_cases_untouched():
    """A local prose correction has an explicit target and no source mutation."""
    entry = {"new_sutra": "उद्यमेन विवेकः", "exposition": ["मूळ शब्द येथे"], "examples": [{"text_mr": "तपासलेला प्रसंग"}]}
    before = deepcopy(entry)
    result = apply_editorial_corrections(entry, [{"field": "exposition.0", "old": "मूळ शब्द", "new": "स्पष्ट शब्द", "reason": "clarity"}])
    assert entry == before
    assert result["exposition"] == ["स्पष्ट शब्द येथे"]
    assert result["new_sutra"] == entry["new_sutra"]
    assert result["examples"] == entry["examples"]


@pytest.mark.parametrize("field", ["new_sutra", "examples.0.text_mr", "id", "number"])
def test_protected_fields_rejected(field):
    """An explanatory overlay cannot change formulas, facts or book identities."""
    with pytest.raises(ValueError, match="protected"):
        apply_editorial_corrections({}, [{"field": field, "old": "a", "new": "b", "reason": "test"}])


@pytest.mark.parametrize("old", ["missing", "", "word"])
def test_ambiguous_or_absent_match_rejected(old):
    """Require exactly one match rather than broad find-and-replace edits."""
    with pytest.raises(ValueError, match="exactly once"):
        apply_editorial_corrections({"application_mr": "word word"}, [{"field": "application_mr", "old": old, "new": "new", "reason": "test"}])


@pytest.fixture
def reviewed_result():
    """Return a synthetic v2-bound draft; no arguments/I/O; fixture errors surface."""
    draft = {"application_mr": "स्पष्ट शब्द येथे", "number": 7,
             "examples": [{"text_mr": "अचूक प्रसंग"}]}
    return {"draft": draft, "review": {"verdict": "PASS", "issues": [],
        "typed_review": {"outcome": "READY", "blocking_issues": [],
                         "advisory_notes": [], "uncertainties": []},
        "reviewed_draft_sha256": canonical_hash(draft), "rubric_sha256": "a" * 64}}


@pytest.mark.parametrize("old", ["मूळ शब्द", "स्पष्ट शब्द"])
def test_v2_exact_copy_never_reapplies_even_matching_ledger(reviewed_result, old):
    """Given old or still-matching ledger text, preserve all bound fields; assertions diagnose changes."""
    correction = [{"field": "application_mr", "old": old, "new": "पुढील बदल", "reason": "legacy"}]
    before = deepcopy(reviewed_result)
    draft = select_reviewed_draft(reviewed_result, correction)
    assert draft == before["draft"] and reviewed_result == before
    evidence = review_selection_evidence(reviewed_result, correction, draft)
    assert evidence["review_binding_verified"] is True
    assert evidence["selected_draft_sha256"] == before["review"]["reviewed_draft_sha256"]
    assert evidence["rubric_sha256"] == "a" * 64
    assert evidence["editorial_overlay_count"] == 0
    assert evidence["post_review_prose_changed"] is False
    draft["examples"][0]["text_mr"] = "copy only"
    assert reviewed_result == before


def test_legacy_selection_keeps_existing_overlay_semantics():
    """Given legacy evidence, return corrected copy with honest unbound provenance; assertions fail on mutation."""
    result = {"draft": {"application_mr": "मूळ शब्द"}, "review": {"verdict": "PASS"}}
    before = deepcopy(result)
    correction = [{"field": "application_mr", "old": "मूळ", "new": "स्पष्ट", "reason": "clarity"}]
    draft = select_reviewed_draft(result, correction)
    assert draft == apply_editorial_corrections(result["draft"], correction)
    assert result == before
    evidence = review_selection_evidence(result, correction, draft)
    assert evidence["mode"] == "legacy_export_overlay"
    assert evidence["review_binding_verified"] is False
    assert evidence["reviewed_draft_sha256"] is None
    assert evidence["editorial_overlay_count"] == 1 and evidence["post_review_prose_changed"]


@pytest.mark.parametrize("field", ["application_mr", "number", "examples"])
def test_v2_any_draft_tampering_rejects_hash(reviewed_result, field):
    """Mutate a bound prose, identity or case field; expect ValueError without fallback."""
    reviewed_result["draft"][field] = "altered"
    with pytest.raises(ValueError, match="hash mismatch"):
        select_reviewed_draft(reviewed_result, [])


@pytest.mark.parametrize("field", ["typed_review", "reviewed_draft_sha256", "rubric_sha256"])
def test_incomplete_v2_binding_cannot_downgrade_to_legacy(reviewed_result, field):
    """Remove one v2 binding field; selection must fail rather than apply legacy overlays."""
    reviewed_result["review"].pop(field)
    with pytest.raises(ValueError, match="V2"):
        select_reviewed_draft(reviewed_result, [])


def test_typed_hold_cannot_hide_behind_legacy_pass(reviewed_result):
    """Keep a misleading PASS wrapper but mark typed uncertainty; selection must reject."""
    reviewed_result["review"]["typed_review"].update(outcome="AUTHOR_REVIEW", uncertainties=["अर्थ तपासावा"])
    with pytest.raises(ValueError, match="held"):
        select_reviewed_draft(reviewed_result, [])
