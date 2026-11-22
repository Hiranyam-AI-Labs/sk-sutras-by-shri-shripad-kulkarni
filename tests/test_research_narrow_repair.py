"""Bound repair cost without weakening the subsequent complete-entry assessment."""

from copy import deepcopy
import pytest
from scripts.run_research_book import (narrow_formula_repair, merge_formula_repair,
    narrow_exposition_repair, merge_exposition_repair)


def test_only_linguistic_findings_use_small_repair():
    """Broader content problems and structural failures require full handling."""
    payload = {"draft": {}, "assessment": {"status": "PASS"}, "review": {"issues": [{"field": "new_sutra"}]}}
    assert narrow_formula_repair(payload)
    payload["review"]["issues"].append({"field": "exposition.0"})
    assert not narrow_formula_repair(payload)
    payload["review"]["issues"] = [{"field": "grammar_mr"}]
    payload["assessment"]["status"] = "NEEDS_REVISION"
    assert not narrow_formula_repair(payload)


def test_narrow_patch_preserves_all_unrelated_text_and_evidence():
    """Only the explicit linguistic fields change; inputs and cases stay intact."""
    payload = {"draft": {"new_sutra": "old", "grammar_mr": "old", "translation_mr": "old", "exposition": ["unchanged"], "examples": [{"fact": "verified"}], "references": ["source"]}}
    before = deepcopy(payload)
    patch = {"new_sutra": "नवः विचारः", "grammar_mr": "व्याकरण", "translation_mr": "नवा विचार"}
    result = merge_formula_repair({"patch": patch}, payload)
    assert payload == before
    assert result == {**before["draft"], **patch}
    result["examples"][0]["fact"] = "different"
    assert payload == before


@pytest.mark.parametrize("patch", [None, {}, {"new_sutra": "x"}, {"new_sutra": "x", "grammar_mr": "y", "translation_mr": "z", "examples": []}])
def test_invalid_patch_cannot_modify_other_fields(patch):
    """Incomplete or wider patches fail before replacing any saved draft."""
    with pytest.raises(ValueError, match="exactly three"):
        merge_formula_repair({"patch": patch}, {"draft": {}})


def test_word_shortfall_repair_preserves_existing_text_and_cases():
    """The observed486-word failure adds only a paragraph, then gets reviewed."""
    payload = {"assessment": {"issues": ["exposition has 486 Devanagari word tokens; at least 500 required"]},
               "review": {"verdict": "PASS"},
               "draft": {"exposition": ["opening", "closing"], "new_sutra": "unchanged", "examples": [{"case_id": "real"}]}}
    before = deepcopy(payload)
    assert narrow_exposition_repair(payload)
    result = merge_exposition_repair({"additional_paragraph_mr": "additional explanation"}, payload)
    assert payload == before
    assert result == {**before["draft"], "exposition": ["opening", "additional explanation", "closing"]}
    payload["review"]["verdict"] = "REVIEW_REQUIRED"
    assert not narrow_exposition_repair(payload)
    payload["review"]["verdict"] = "PASS"
    payload["assessment"]["issues"].append("Wrong reference")
    assert not narrow_exposition_repair(payload)


@pytest.mark.parametrize("answer", [{}, {"additional_paragraph_mr": ""}, {"additional_paragraph_mr": "x", "new_sutra": "y"}])
def test_word_repair_rejects_empty_or_broader_patch(answer):
    """An append-only repair cannot replace the formula or other chapter data."""
    with pytest.raises(ValueError, match="one nonempty"):
        merge_exposition_repair(answer, {"draft": {"exposition": ["keep"]}})
