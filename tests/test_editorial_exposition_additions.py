"""Offline local exposition additions and immutable-seed resume regressions."""

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import run_research_book as runner
from src.orchestration.independent_review import canonical_hash
from src.orchestration.research_acceptance import _devanagari_word
from src.orchestration.research_council import ResearchCouncil, VOICES, TEXT_FIELDS, _json


def seed(words=499):
    """Return a synthetic complete composition with an exact script-word count."""
    return {**{k: "स्थानिक पुरावा" for k in TEXT_FIELDS}, "id": "NEW-025",
            "new_sutra": "उद्यमेन विवेकः", "number": 25, "chapter": 5,
            "exposition": ["विचार " * (words - 1), "कृती"], "references": ["S1"],
            "comparative_mr": [], "examples": [], "dos_mr": [], "donts_mr": []}


def addition(draft, words=42):
    """Bind a local paragraph to the exact original council serialization."""
    return {25: {"seed_sha256": hashlib.sha256(_json(draft).encode()).hexdigest(),
                 "paragraph_mr": "तपासा " * words}}


def council(path, additions, final=None, overrides=None):
    """Build local callbacks that forbid paid composition; return council/reviewer."""
    writer = Mock(side_effect=AssertionError("No paid composition expected"))
    final = final or Mock(return_value={"outcome": "READY", "verdict": "PASS", "issues": []})
    obj = ResearchCouncil(path, {v: writer for v in VOICES}, Mock(),
                          lambda *args: {"status": "PASS", "issues": []}, max_revisions=1,
                          final_review=final, editorial_additions=additions, draft_overrides=overrides)
    return obj, final


def save_seed(path, draft):
    """Insert a paid seed fixture once; never generate or alter production evidence."""
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO research_stages VALUES (25,'composition','sutrakar','original-request',?)", (_json(draft),))


def execute(obj):
    """Run just current-draft composition selection and independent review locally."""
    return obj._compose_current_review({"number": 25, "sources": {}, "prior_formulas": [],
                                       "forbidden_originals": [], "used_case_ids": []}, {}, {}, {})


def test_three_resumes_ignore_typed_archival_override_and_add_once(tmp_path):
    """Every resume starts at the 499-word seed, even with amended export snapshots."""
    original = seed()
    additions = addition(original)
    path = tmp_path / "council.db"
    first, _ = council(path, additions)
    save_seed(path, original)
    candidates = {str(n): {"draft": {**seed(), "number": n}} for n in (5, 8, 9)}
    (tmp_path / "revision_candidates_v2.json").write_text(json.dumps(candidates), encoding="utf-8")
    (tmp_path / "editorial_corrections.json").write_text('{}', encoding="utf-8")
    outcomes = []
    for index in range(3):
        overrides = runner.load_draft_overrides(tmp_path, 25, additions)
        assert 25 not in overrides
        obj, final = council(path, additions, overrides=overrides)
        result = execute(obj)
        amended = result["draft"]
        assert amended["exposition"] == [original["exposition"][0], additions[25]["paragraph_mr"], original["exposition"][-1]]
        assert {k: v for k, v in amended.items() if k != "exposition"} == {k: v for k, v in original.items() if k != "exposition"}
        assert final.call_args.args[0]["draft"] == amended
        assert canonical_hash(amended) != canonical_hash(original)
        assert result["revisions"] == 0
        assert result["editorial_addition"]["provenance"] == "local_editorial"
        assert result["editorial_addition"]["provider_calls"] == 0
        assert result["editorial_addition"]["original_words"] == 499
        outcomes.append(deepcopy(result))
        result["review"].update(typed_review={}, reviewed_draft_sha256=canonical_hash(amended))
        text = json.dumps(result, ensure_ascii=False)
        (tmp_path / "entry-025.json").write_text(text, encoding="utf-8")
        if index == 0:
            (tmp_path / "pre_v2_results").mkdir()
            (tmp_path / "pre_v2_results/entry-025.json").write_text(text, encoding="utf-8")
    assert outcomes[0] == outcomes[1] == outcomes[2]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT stage,response_json FROM research_stages").fetchall() == [("composition", _json(original))]
        assert db.execute("SELECT COUNT(*) FROM research_attempts").fetchone() == (0,)


@pytest.mark.parametrize("original_words,added_words", [(500, 42), (449, 60), (499, 19), (450, 20)])
def test_word_count_boundaries_reject_before_review(tmp_path, original_words, added_words):
    """Only a real near-minimum gap with enough substantive script words qualifies."""
    draft = seed(original_words)
    obj, final = council(tmp_path / "c.db", addition(draft, added_words))
    save_seed(obj.path, draft)
    with pytest.raises(ValueError, match="450-499"):
        execute(obj)
    final.assert_not_called()


def test_hash_drift_rejects_before_review(tmp_path):
    """A supplied paragraph cannot attach to another original seed."""
    draft = seed()
    additions = addition(draft)
    additions[25]["seed_sha256"] = "0" * 64
    obj, final = council(tmp_path / "c.db", additions)
    save_seed(obj.path, draft)
    with pytest.raises(ValueError, match="seed hash"):
        execute(obj)
    final.assert_not_called()


def test_existing_paid_repair_is_not_modified(tmp_path):
    """Existing repaired selection wins; local additions only apply to unrepaired seeds."""
    original = seed()
    obj, final = council(tmp_path / "c.db", addition(original))
    save_seed(obj.path, original)
    repaired = seed(550)
    with sqlite3.connect(obj.path) as db:
        db.execute("INSERT INTO research_v2_lineage VALUES (?,?)", (25, addition(original)[25]["seed_sha256"]))
        db.execute("INSERT INTO research_stages VALUES (25,'composition_v2_1','sutrakar','repair-request',?)", (_json(repaired),))
    result = execute(obj)
    assert result["draft"] == repaired and "editorial_addition" not in result
    assert final.call_args.args[0]["draft"] == repaired


def test_invalid_review_stops_without_sutrakar_rewrite(tmp_path):
    """A new review failure does not authorize a paid rewrite of the local addition."""
    draft = seed()
    final = Mock(side_effect=RuntimeError("Invalid independent review"))
    obj, _ = council(tmp_path / "c.db", addition(draft), final)
    save_seed(obj.path, draft)
    with pytest.raises(RuntimeError, match="Invalid independent"):
        execute(obj)
    assert final.call_args.args[0]["draft"]["exposition"] != draft["exposition"]
    obj.voices["sutrakar"].assert_not_called()


def test_optional_loader_and_revision_conflict(tmp_path):
    """Read exact mapping values and reject competing explicit candidate seeds."""
    assert runner.load_editorial_additions(tmp_path) == {}
    value = addition(seed())
    (tmp_path / "editorial_exposition_additions.json").write_text(json.dumps(value), encoding="utf-8")
    assert runner.load_editorial_additions(tmp_path) == value
    candidates = {str(n): {"draft": {**seed(), "number": n}} for n in (5, 8, 9, 25)}
    (tmp_path / "revision_candidates_v2.json").write_text(json.dumps(candidates), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicts"):
        runner.load_draft_overrides(tmp_path, 25, value)


def test_actual_parent_addition_uses_exact_original_seed(tmp_path):
    """Validate the supplied entry-25 paragraph locally without changing its file."""
    work = Path(__file__).resolve().parents[1] / "logs/author-research-generation-20261118"
    if not (work / "editorial_exposition_additions.json").exists():
        pytest.skip("Parent's optional editorial sidecar is absent")
    additions = runner.load_editorial_additions(work)
    with sqlite3.connect((work / "council.db").as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT response_json FROM research_stages WHERE number=25 AND stage='composition' AND speaker='sutrakar'").fetchone()
    original = json.loads(row[0])
    obj, final = council(tmp_path / "c.db", additions)
    save_seed(obj.path, original)
    result = execute(obj)
    assert result["editorial_addition"]["original_words"] == 499
    assert result["draft"]["exposition"][-2] == additions[25]["paragraph_mr"]
    assert sum(_devanagari_word(t) for p in result["draft"]["exposition"] for t in p.split()) >= 500


@pytest.mark.parametrize("archive_kind", ["typed", "legacy"])
def test_repaired_24_resume_skips_typed_archive_but_keeps_legacy_override(tmp_path, archive_kind):
    """Without additions, typed repaired outputs never replace immutable seed lineage.

    Legacy archives remain valid seed overrides. Two resumes reuse the saved
    repair, preserve both paid stages, and make no writer calls.
    """
    original = {**seed(520), "number": 24, "id": "NEW-024"}
    repaired = deepcopy(original)
    repaired["grammar_mr"] = "दुरुस्त व्याकरण"
    typed = {"draft": repaired, "review": {
        "typed_review": {"outcome": "READY", "blocking_issues": [], "uncertainties": []},
        "verdict": "PASS", "reviewed_draft_sha256": canonical_hash(repaired),
        "rubric_sha256": "a" * 64}}
    archive = typed if archive_kind == "typed" else {"draft": original, "review": {"verdict": "PASS"}}
    candidates = {str(n): {"draft": {**seed(), "number": n}} for n in (5, 8, 9)}
    (tmp_path / "revision_candidates_v2.json").write_text(json.dumps(candidates), encoding="utf-8")
    (tmp_path / "editorial_corrections.json").write_text('{}', encoding="utf-8")
    (tmp_path / "entry-024.json").write_text(json.dumps(typed), encoding="utf-8")
    (tmp_path / "pre_v2_results").mkdir()
    (tmp_path / "pre_v2_results/entry-024.json").write_text(json.dumps(archive), encoding="utf-8")
    path = tmp_path / "council.db"
    council(path, {})  # Create only the local checkpoint schema.
    expected_stages = [("composition", _json(original)), ("composition_v2_1", _json(repaired))]
    seed_hash = hashlib.sha256(_json(original).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        for stage, value in expected_stages:
            db.execute("INSERT INTO research_stages VALUES (24,?,'sutrakar','saved-request',?)", (stage, value))
        db.execute("INSERT INTO research_v2_lineage VALUES (24,?)", (seed_hash,))
    for _ in range(2):
        overrides = runner.load_draft_overrides(tmp_path, 24, {})
        if archive_kind == "typed":
            assert 24 not in overrides
        else:
            assert overrides[24] == original
        obj, final = council(path, {}, overrides=overrides)
        result = obj._compose_current_review({"number": 24, "sources": {}, "prior_formulas": [],
                                             "forbidden_originals": [], "used_case_ids": []}, {}, {}, {})
        assert result["draft"] == repaired and result["revisions"] == 1
        assert "editorial_addition" not in result
        assert final.call_args.args[0]["draft"] == repaired
        obj.voices["sutrakar"].assert_not_called()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT stage,response_json FROM research_stages ORDER BY stage").fetchall() == expected_stages
        assert db.execute("SELECT seed_hash FROM research_v2_lineage WHERE number=24").fetchone() == (seed_hash,)
