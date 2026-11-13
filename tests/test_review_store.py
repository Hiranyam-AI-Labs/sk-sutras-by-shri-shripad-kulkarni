"""Version and approval transitions must remain fail closed across restarts."""

import tempfile
import importlib.util
from pathlib import Path

import pytest

from src.agents.acceptance_policy import GATE_NAMES, POLICY_VERSION
from tests.test_example_registry_unittest import ExampleRegistry
module_path = Path(__file__).resolve().parents[1] / "src" / "orchestration" / "review_store.py"
spec = importlib.util.spec_from_file_location("review_store_standalone", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ReviewStore, fingerprint = module.ReviewStore, module.fingerprint


def test_stage_checkpoint_rejects_tampered_response():
    """A persisted role output is reused only when its stored hash still matches."""
    with tempfile.TemporaryDirectory() as folder:
        store = ReviewStore(Path(folder) / "review.db")
        store.save_stage_checkpoint("run", "narada_specialist", "request-hash",
                                    {"thesis": "grounded", "source_reference": "Narada 1"})
        assert store.stage_checkpoint("run", "narada_specialist", "request-hash")["thesis"] == "grounded"
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(store.path)) as db:
            db.execute("UPDATE council_stage_checkpoints SET response_json=? WHERE run_id=?",
                       ('{"thesis":"tampered"}', "run"))
            db.commit()
        with pytest.raises(ValueError, match="integrity"):
            store.stage_checkpoint("run", "narada_specialist", "request-hash")


def report(status="PASS"):
    """Return synthetic complete policy evidence for storage boundary tests."""
    return {"policy_version": POLICY_VERSION, "gates": {name: status for name in GATE_NAMES}}


def test_approval_exact_version_and_manifest():
    """A content edit invalidates prior approvals and stale publication fails."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "reviews.db"
        store = ReviewStore(path)
        registry = ExampleRegistry(Path(folder) / "examples.db")
        registry.register("Founder One", "PERSON", "documented case")
        draft = {"sanskrit": "सत्यं कार्यम्", "named_examples": [
            {"name": "Founder One", "polarity": "POSITIVE", "location": "case"}]}
        v1 = store.save_draft("one", draft, report())
        with pytest.raises(ValueError):
            store.approve("one", v1, "AUTHOR", "Author", fingerprint(draft))
        store.mark_ai_validated("one", v1)
        store.approve("one", v1, "SCHOLAR", "Scholar", fingerprint(draft))
        store.approve("one", v1, "AUTHOR", "Author", fingerprint(draft))
        with pytest.raises(ValueError):
            ReviewStore(path).freeze_manifest("unallocated", [("one", v1)], registry)
        registry.reserve("one", draft["named_examples"], fingerprint(draft))
        registry.commit("one")
        assert ReviewStore(path).freeze_manifest("first", [("one", v1)], registry)["units"][0]["content"] == draft
        v2 = store.save_draft("one", {"sanskrit": "धर्मः कार्यम्"}, report())
        assert v2 == 2
        with pytest.raises(ValueError):
            store.freeze_manifest("stale", [("one", v1)], registry)
        with pytest.raises(ValueError):
            store.approve("one", v2, "SCHOLAR", "Scholar", fingerprint(draft))


def test_failed_gate_blocks_ai_validation():
    """A persisted failed gate cannot be promoted by a separate score."""
    with tempfile.TemporaryDirectory() as folder:
        store = ReviewStore(Path(folder) / "reviews.db")
        version = store.save_draft("one", {"score": 99}, report("FAIL"))
        with pytest.raises(ValueError):
            store.mark_ai_validated("one", version)


def test_interrupted_run_keeps_revision_limit_across_store_restart():
    """A crash consumes its attempt and a new handle cannot restart from one."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "reviews.db"
        first = ReviewStore(path)
        assert first.start_attempt("pilot", "one", 3) == 1
        assert ReviewStore(path).start_attempt("pilot", "one", 3) == 2
        assert ReviewStore(path).start_attempt("pilot", "one", 3) == 3
        with pytest.raises(ValueError, match="limit exhausted"):
            ReviewStore(path).start_attempt("pilot", "one", 3)


def test_one_time_precomposition_correction_requires_no_draft():
    """Technical call history can be reclassified once, with a durable record."""
    with tempfile.TemporaryDirectory() as folder:
        store = ReviewStore(Path(folder) / "reviews.db")
        store.start_attempt("pilot", "one", 3)
        assert store.correct_precomposition_attempts("pilot", "one") == 1
        assert ReviewStore(store.path).run_progress("pilot", "one")["attempts"] == 0
        with pytest.raises(ValueError, match="uncorrected"):
            store.correct_precomposition_attempts("pilot", "one")
