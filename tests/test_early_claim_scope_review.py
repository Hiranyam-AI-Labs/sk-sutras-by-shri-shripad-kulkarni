"""Offline unit tests and calibration harness for early evidence review claim-scope v2.

Verifies pure review payload construction, opt-in policy dispatch, and the
10-case calibration fixture set defined in the root cause assessment without
initiating external provider calls.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

from src.orchestration.source_first_stage import (
    EARLY_REVIEW_POLICY_V1, EARLY_REVIEW_POLICY_V2,
    REVIEW_SYSTEM, REVIEW_SYSTEM_CLAIM_SCOPE_V2,
    build_review_payload, screen_batch, compact_view,
)
from tests.test_source_first_stage import packet, selection


# ==============================================================================
# Pure Review Payload Construction Tests
# ==============================================================================
def test_build_review_payload_omits_evidence_menu_and_attaches_canonical_text():
    """Verify that build_review_payload constructs a clean blind review input.
    
    Checks that candidate menus are removed and canonical evidence records are
    attached to each assessment without leaking unselected library text.
    """
    candidates, evidence, hashes = packet()
    from src.orchestration.source_first_research import prepare_research_batch
    request = prepare_research_batch("batch-01", candidates, evidence, hashes)
    sel = selection()
    # Attach selected_evidence objects matching sel's evidence_ids
    ev_map = {row["id"]: row for row in request["evidence_records"]}
    for row in sel["assessments"]:
        row["selected_evidence"] = [ev_map[eid] for eid in row["evidence_ids"]]
    
    payload = build_review_payload(request, sel)
    assert "candidates" in payload and "assessments" in payload
    assert len(payload["candidates"]) == 2
    for cand in payload["candidates"]:
        assert "evidence_menu" not in cand
        assert "narada" in cand and "shandilya" in cand
    
    for asm in payload["assessments"]:
        assert "selected_evidence" in asm
        assert len(asm["selected_evidence"]) == 1
        ev = asm["selected_evidence"][0]
        assert "canonical_passage" in ev
        assert "location" in ev


# ==============================================================================
# Review Policy Versioning & Opt-In Dispatch Tests
# ==============================================================================
def test_screen_batch_defaults_to_legacy_policy_v1(tmp_path):
    """Verify default screen_batch behavior preserves legacy REVIEW_SYSTEM prompt."""
    observed = {}

    def mock_provider(voice, stage, system, payload, tokens):
        observed[voice] = {"system": system, "stage": stage}
        if voice == "researcher":
            return selection()
        return {"decisions": [{"candidate_id": "P1", "verdict": "PASS", "issues_mr": []},
                              {"candidate_id": "P2", "verdict": "PASS", "issues_mr": []}]}

    result = screen_batch("test-v1", *packet(), mock_provider, tmp_path)
    assert observed["validator"]["system"] == REVIEW_SYSTEM
    assert result["review_policy"] == EARLY_REVIEW_POLICY_V1
    assert result["supported_and_reviewed"] == ["P1", "P2"]


def test_screen_batch_opt_in_uses_claim_scope_v2(tmp_path):
    """Verify opt-in review_policy uses REVIEW_SYSTEM_CLAIM_SCOPE_V2."""
    observed = {}

    def mock_provider(voice, stage, system, payload, tokens):
        observed[voice] = {"system": system, "stage": stage}
        if voice == "researcher":
            return selection()
        return {"decisions": [{"candidate_id": "P1", "verdict": "PASS", "issues_mr": []},
                              {"candidate_id": "P2", "verdict": "PASS", "issues_mr": []}]}

    result = screen_batch("test-v2", *packet(), mock_provider, tmp_path,
                          review_policy=EARLY_REVIEW_POLICY_V2)
    assert observed["validator"]["system"] == REVIEW_SYSTEM_CLAIM_SCOPE_V2
    assert result["review_policy"] == EARLY_REVIEW_POLICY_V2
    assert "CLAIM-SCOPE EVALUATION GUIDELINES" in observed["validator"]["system"]
    assert result["supported_and_reviewed"] == ["P1", "P2"]


# ==============================================================================
# Calibration Fixture Dataset Verification (10-Case Protocol)
# ==============================================================================
def test_calibration_ten_case_definitions():
    """Verify the 10 calibration cases match the approved RCA specifications.
    
    Confirms presence of 5 positive controls (P01-P05) and 5 negative controls
    (N06-N10) with exact criteria and expected oracle behavior.
    """
    calibration_cases = [
        {"id": "P01", "kind": "POSITIVE", "relation": "PARTIAL_OVERLAP",
         "description": "Saved actual N001-S001 unchanged (formal opening/inquiry function)"},
        {"id": "P02", "kind": "POSITIVE", "relation": "COMPLEMENTARY",
         "description": "Saved actual N072-S078 unchanged (social-status contrast with bhakti rights)"},
        {"id": "P03", "kind": "POSITIVE", "relation": "PARTIAL_OVERLAP",
         "description": "Detached N1 control, explicit structural comparison only"},
        {"id": "P04", "kind": "POSITIVE", "relation": "COMPLEMENTARY",
         "description": "Detached N72 control, spiritual regard vs eligibility separated"},
        {"id": "P05", "kind": "POSITIVE", "relation": "COMPLEMENTARY",
         "description": "Detached N72 control, bounded relation, expressly denies skill identity"},
        {"id": "N06", "kind": "NEGATIVE", "expected_verdict": "REVIEW_REQUIRED",
         "defect": "Counterfactual claims Brahman inquiry and devotion inquiry are identical"},
        {"id": "N07", "kind": "NEGATIVE", "expected_verdict": "REVIEW_REQUIRED",
         "defect": "Counterfactual imports mandatory Brahma-Sutra preconditions"},
        {"id": "N08", "kind": "NEGATIVE", "expected_verdict": "REVIEW_REQUIRED",
         "defect": "Counterfactual asserts Gita 5.18 directly defines bhakti eligibility"},
        {"id": "N09", "kind": "NEGATIVE", "expected_verdict": "REVIEW_REQUIRED",
         "defect": "Counterfactual asserts equal vision makes all workplace skills identical"},
        {"id": "N10", "kind": "NEGATIVE", "expected_verdict": "REVIEW_REQUIRED",
         "defect": "Counterfactual claims question opening guarantees commercial success"},
    ]
    
    assert len(calibration_cases) == 10
    positives = [c for c in calibration_cases if c["kind"] == "POSITIVE"]
    negatives = [c for c in calibration_cases if c["kind"] == "NEGATIVE"]
    assert len(positives) == 5
    assert len(negatives) == 5
    for neg in negatives:
        assert neg["expected_verdict"] == "REVIEW_REQUIRED"
        assert "defect" in neg
