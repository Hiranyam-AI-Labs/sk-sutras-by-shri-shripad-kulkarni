"""Regression checks for the versioned, fail-closed Udyam acceptance boundary."""

from src.agents.acceptance_policy import GATE_NAMES, evaluate_policy


def test_missing_assessments_cannot_be_approved():
    """A score or plausible draft cannot fill absent scholarly evidence; inspect gates on failure."""
    draft = {"original_sanskrit_verse": "सत्यं व्यवसायस्य मूलम्।",
             "comprehensive_bhashya_mr": "शब्द " * 80,
             "padaccheda": "सत्यं व्यवसायस्य मूलम्", "anvaya": "सत्यं मूलम्",
             "nirukta": "सत्य", "translation_en": "Truth is foundational.",
             "translation_mr": "सत्य हाच पाया.", "biographical_case_studies": [{}, {}]}
    result = evaluate_policy(draft)
    assert len(result["gates"]) == 15
    assert result["overall_status"] == "NEEDS_REVISION"
    assert result["gates"]["narada_fidelity"] == "NOT_EVALUATED"


def test_high_score_cannot_override_deterministic_failure():
    """The verifier cannot waive an overlong Bhashya; issues identify the failed gate."""
    draft = {"original_sanskrit_verse": "सत्यं व्यवसायस्य मूलम्।",
             "comprehensive_bhashya_mr": "शब्द " * 111,
             "biographical_case_studies": [{}, {}]}
    assessments = {name: {"status": "PASS", "evidence": "Inspected."} for name in GATE_NAMES}
    result = evaluate_policy(draft, assessments)
    assert result["gates"]["bhashya_length"] == "FAIL"
    assert result["overall_status"] == "NEEDS_REVISION"


def test_duplicate_canon_blocks_candidate():
    """A prior formulation blocks reuse even when the verifier marks all gates passed."""
    draft = {"original_sanskrit_verse": "सत्यं व्यवसायस्य मूलम्।",
             "comprehensive_bhashya_mr": "शब्द " * 80,
             "biographical_case_studies": [{}, {}]}
    assessments = {name: {"status": "PASS", "evidence": "Inspected."} for name in GATE_NAMES}
    result = evaluate_policy(draft, assessments, ["सत्यं व्यवसायस्य मूलम्॥"])
    assert result["gates"]["canon_duplicates"] == "FAIL"
    assert result["overall_status"] == "NEEDS_REVISION"


def test_verifier_failure_survives_objective_length_pass():
    """A valid word count cannot erase a scholarly failure on its content."""
    draft = {"original_sanskrit_verse": "सत्यं व्यवसायस्य मूलम्",
             "comprehensive_bhashya_mr": "शब्द " * 80}
    assessments = {"bhashya_length": {"status": "FAIL", "evidence": "Padding obscures meaning."},
                   "short_formulation": {"status": "FAIL", "evidence": "Unidiomatic wording."}}
    result = evaluate_policy(draft, assessments)
    assert result["gates"]["bhashya_length"] == "FAIL"
    assert result["gates"]["short_formulation"] == "FAIL"
