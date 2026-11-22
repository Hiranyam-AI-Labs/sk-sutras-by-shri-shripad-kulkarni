"""Offline checkpoint and production-gate regressions; all providers are forbidden."""

import json
from copy import deepcopy
import pytest

from src.orchestration.research_council import ResearchCouncil, VOICES, TEXT_FIELDS
from scripts import run_research_book as runner


def draft():
    """Return a complete small schema fixture; semantic checks use a local fake."""
    return {**{k: "local evidence" for k in TEXT_FIELDS}, "new_sutra": "उद्यमेन विवेकः",
            "number": 1, "chapter": 1, "exposition": ["local explanation"],
            "references": [], "comparative_mr": [], "examples": [], "dos_mr": [], "donts_mr": []}


def fixture_council(path, final_review=None, overrides=None, repair_limit=1):
    """Build observable local four-agent callbacks and isolated reviewer; no network."""
    calls = []
    def voice(name):
        """Bind one fake voice; return exact stage schemas and retain call evidence."""
        def answer(p):
            """Answer one stage using local data; unexpected stages fail the test."""
            calls.append((name, p["stage"]))
            stage = p["stage"]
            if stage == "position": return {"thesis": name}
            if stage == "challenge": return {"challenges": {v: "why" for v in VOICES if v != name}}
            if stage == "reply": return {"answers": {v: "evidence" for v in VOICES if v != name}}
            if stage == "proposal": return {"proposed_sutra": "उद्यमेन विवेकः"}
            if stage == "peer_review": return {"verdict": "PASS", "issues": []}
            if stage.startswith("composition"): return draft()
            raise AssertionError(stage)
        return answer
    def legacy(p):
        """Return a legacy pass only for initial cache seeding."""
        calls.append(("validator", p["stage"]))
        return {"verdict": "PASS", "issues": []}
    return ResearchCouncil(path, {v: voice(v) for v in VOICES}, legacy,
        lambda *args: {"status": "PASS", "issues": []}, max_revisions=repair_limit,
        final_review=final_review, draft_overrides=overrides), calls


def execute(council):
    """Run one offline entry with stable canonical inputs for replay checks."""
    return council.run(1, {"reader_question": "business"}, {"references": [], "examples": []}, [], [], set())


def test_corrected_draft_reuses_discussion_without_replaying_claude(tmp_path):
    """A new final review sees exact corrected text; no paid-stage replay occurs."""
    path = tmp_path / "council.db"
    old, _ = fixture_council(path)
    execute(old)
    revised = draft(); revised["grammar_mr"] = "corrected explanation"
    seen = []
    def final(p):
        """Record fresh current payload and reject any prior reviewer opinions."""
        seen.append(deepcopy(p))
        assert "peer_concerns" not in p and "prior_review" not in p
        return {"outcome": "READY", "verdict": "PASS", "issues": []}
    new, calls = fixture_council(path, final, {1: revised})
    result = execute(new)
    assert calls == []
    assert seen[0]["draft"] == revised
    assert result["draft"] == revised and result["status"] == "READY_FOR_AUTHOR_REVIEW"


def test_uncertain_review_never_requests_writer_repair(tmp_path):
    """Editorial uncertainty remains held rather than triggering a paid rewrite."""
    council, calls = fixture_council(tmp_path / "c.db", lambda p: {
        "outcome": "AUTHOR_REVIEW", "verdict": "REVIEW_REQUIRED", "issues": []})
    assert execute(council)["status"] == "NEEDS_REVIEW"
    assert [s for _, s in calls if s.startswith("composition")] == ["composition"]


def test_invalid_review_stops_without_writer_retry(tmp_path):
    """A failed review is not misclassified as a content-repair instruction."""
    def invalid(p):
        """Simulate the versioned cache rejecting unsupported review evidence."""
        raise RuntimeError("Invalid objection")
    council, calls = fixture_council(tmp_path / "c.db", invalid)
    with pytest.raises(RuntimeError, match="Invalid objection"):
        execute(council)
    assert [s for _, s in calls if s.startswith("composition")] == ["composition"]


def test_zero_repair_budget_is_respected(tmp_path):
    """No v2 repair may bypass an explicit zero-revision budget."""
    council, calls = fixture_council(tmp_path / "c.db", lambda p: {
        "outcome": "REVISION_REQUIRED", "verdict": "REVIEW_REQUIRED", "issues": []}, repair_limit=0)
    assert execute(council)["status"] == "NEEDS_REVIEW"
    assert not any(s == "composition_v2_1" for _, s in calls)


def test_missing_calibration_stops_before_credentials(tmp_path, monkeypatch):
    """Production entry point cannot access providers before calibration passes."""
    monkeypatch.setattr(runner, "WORK", tmp_path)
    def forbidden(*args):
        """Fail if credential loading occurs before the calibration gate."""
        raise AssertionError("Credentials must not be read")
    monkeypatch.setattr(runner, "load_project_credentials", forbidden)
    with pytest.raises(FileNotFoundError):
        runner.run(100, 5., "forbidden", review_v2=True)


def test_failed_calibration_stops_before_credentials(tmp_path, monkeypatch):
    """A populated but failed calibration cannot enable a full paid run."""
    monkeypatch.setattr(runner, "WORK", tmp_path)
    (tmp_path / "validator-calibration-approved.json").write_text(json.dumps({"status": "FAIL"}))
    (tmp_path / "validator_calibration_v2.json").write_text(json.dumps({"fixtures": []}))
    with pytest.raises(ValueError):
        runner.run(100, 5., "forbidden", review_v2=True)


def test_public_runner_cannot_disable_calibration():
    """Reject a public legacy-mode request before any credential or filesystem access."""
    with pytest.raises(ValueError, match="requires versioned"):
        runner.run(100, 5., "forbidden", review_v2=False)


def test_repaired_checkpoint_binds_original_corrected_seed(tmp_path):
    """Replay identical seeds locally, but never silently discard a newer correction."""
    path = tmp_path / "c.db"
    old, _ = fixture_council(path)
    execute(old)
    revised = draft(); revised["grammar_mr"] = "corrected seed"
    def review(p):
        """Request one repair for the seed, then accept the fake repaired draft."""
        ready = p["draft"]["grammar_mr"] != "corrected seed"
        return {"outcome": "READY" if ready else "REVISION_REQUIRED",
                "verdict": "PASS" if ready else "REVIEW_REQUIRED", "issues": []}
    current, _ = fixture_council(path, review, {1: revised})
    assert execute(current)["status"] == "READY_FOR_AUTHOR_REVIEW"
    replay, calls = fixture_council(path, review, {1: revised})
    assert execute(replay)["status"] == "READY_FOR_AUTHOR_REVIEW" and not calls
    changed = deepcopy(revised); changed["grammar_mr"] = "newer correction"
    stale, calls = fixture_council(path, review, {1: changed})
    with pytest.raises(ValueError, match="Changed v2 composition seed"):
        execute(stale)
    assert not calls
