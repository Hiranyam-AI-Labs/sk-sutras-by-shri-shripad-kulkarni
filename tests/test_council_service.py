"""All five roles exercise the bounded council without a paid provider call."""

import tempfile
from pathlib import Path
import pytest

from src.agents.acceptance_policy import GATE_NAMES
from src.database.example_registry import ExampleRegistry
from src.orchestration.council_service import CouncilService
from src.orchestration.review_store import ReviewStore


def make_draft(verse="सत्यं व्यवसायस्य मूलम्"):
    """Construct one complete synthetic chapter candidate for offline role tests."""
    passage = "Verified ethics passage"
    return {"original_sanskrit_verse": verse, "padaccheda": "सत्यं व्यवसायस्य मूलम्",
            "anvaya": "सत्यं मूलम्", "nirukta": "सत्य", "translation_en": "Truth is foundational",
            "translation_mr": "सत्य हा पाया", "comprehensive_bhashya_mr": "शब्द " * 80,
            "biographical_case_studies": [
                {"region": "EASTERN", "person": "Person A", "business": "Firm A", "provenance": "Record A"},
                {"region": "WESTERN", "person": "Person B", "business": "Firm B", "provenance": "Record B"}],
            "dos_and_donts": {"dos": ["one", "two", "three"], "donts": ["one", "two", "three"]},
            "business_assessment": {key: key for key in
                                    ("context", "reader", "decision", "action", "source_rationale")},
            "named_examples": [{"name": "Person A", "polarity": "POSITIVE", "location": "case"}],
            "example_note": passage}


def make_roles(drafts, role_calls):
    """Return deterministic role callbacks and record each responsibility invoked."""
    def narada(source, feedback=None):
        """Return source thesis with optional targeted defect feedback."""
        role_calls.append("narada")
        return "thesis"

    def shandilya(thesis, candidates, feedback=None):
        """Return candidate review with optional source revision feedback."""
        role_calls.append("shandilya")
        return "candidate review"

    def researcher(source, pairing, passages, feedback):
        """Return independent source findings and a bridge for both prompts."""
        role_calls.append("researcher")
        return {"bridge": "Bridge", "findings": ["source corroborated"]}

    def sutrakar(mode, *inputs):
        """Arbitrate independently or compose the next candidate draft."""
        role_calls.append(f"sutrakar:{mode}")
        if mode == "arbitrate":
            return {"accepted": True}
        if mode == "consult":
            return {"findings": ["independent analysis"], "challenges": ["test source fit"]}
        return drafts.pop(0)

    def validator(draft, research, passages, feedback, evidence_context):
        """Supply explicit evidence for each scholarly gate; deterministic checks still apply."""
        assert evidence_context["bridge"] == "Bridge"
        assert evidence_context["passages"] == passages
        assert evidence_context["challenge_response"]["findings"]
        role_calls.append("validator")
        return {"gates": {name: {"status": "PASS", "evidence": "Inspected synthetic fixture"}
                          for name in GATE_NAMES}}

    return {"narada": narada, "shandilya": shandilya, "researcher": researcher,
            "sutrakar": sutrakar, "validator": validator}


def test_five_roles_revise_and_pause_for_human():
    """A failed first draft persists, revises, then stops before human approval."""
    with tempfile.TemporaryDirectory() as folder:
        registry = ExampleRegistry(Path(folder) / "examples.db")
        registry.register("Person A", "PERSON", "Record A")
        store = ReviewStore(Path(folder) / "reviews.db")
        calls = []
        roles = make_roles([make_draft("दीर्घं नूतनं वाक्यं अनेकानि पदानि युक्तम्"), make_draft()], calls)
        result = CouncilService(roles, store, registry).run_unit(
            "chapter-1", {"sanskrit": "source"}, [{"sanskrit": "match"}],
            [{"source_id": "DOC-01", "text": "Verified ethics passage"}])
        assert result["status"] == "HUMAN_REVIEW_PENDING"
        assert result["version"] == 2
        assert len(result["history"]) == 2
        assert calls.count("validator") == 2
        assert "researcher" in calls and "sutrakar:arbitrate" in calls and "sutrakar:consult" in calls


def test_shortfall_is_explicit_and_no_false_approval():
    """All failed attempts return a partial result and retain each draft."""
    with tempfile.TemporaryDirectory() as folder:
        store = ReviewStore(Path(folder) / "reviews.db")
        registry = ExampleRegistry(Path(folder) / "examples.db")
        calls = []
        bad = "अत्यन्तं दीर्घं वाक्यं अनेकपदानि समाहितानि पुनरपि"
        result = CouncilService(make_roles([make_draft(bad), make_draft(bad)], calls),
                                store, registry, max_attempts=2).run_unit(
            "chapter-1", {"sanskrit": "source"}, [{"sanskrit": "match"}],
            [{"source_id": "DOC-01", "text": "Verified ethics passage"}])
        assert result["status"] == "PARTIAL_BLOCKED"
        assert [item["version"] for item in result["history"]] == [1, 2]


def test_missing_sources_stop_before_any_role_call():
    """No evidence packet means no paid role could be called by the service."""
    with tempfile.TemporaryDirectory() as folder:
        calls = []
        service = CouncilService(make_roles([make_draft()], calls),
                                 ReviewStore(Path(folder) / "reviews.db"),
                                 ExampleRegistry(Path(folder) / "examples.db"))
        with pytest.raises(ValueError):
            service.run_unit("chapter-1", {"sanskrit": "source"}, [{"sanskrit": "match"}], [])
        assert calls == []


def test_existing_canon_duplicate_cannot_pass():
    """A verifier PASS on all gates cannot waive a persisted canon duplicate."""
    with tempfile.TemporaryDirectory() as folder:
        draft = make_draft()
        service = CouncilService(make_roles([draft], []),
                                 ReviewStore(Path(folder) / "reviews.db"),
                                 ExampleRegistry(Path(folder) / "examples.db"), max_attempts=1)
        result = service.run_unit("chapter-1", {"sanskrit": "source"},
                                  [{"sanskrit": "match"}],
                                  [{"source_id": "DOC-01", "text": "Verified ethics passage"}],
                                  [draft["original_sanskrit_verse"]])
        assert result["status"] == "PARTIAL_BLOCKED"
        assert result["history"][0]["status"] == "NEEDS_REVISION"
