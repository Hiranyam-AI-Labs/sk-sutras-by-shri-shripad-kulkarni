"""Exact-version review API authorization and sequence tests without server startup."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from src.agents.acceptance_policy import GATE_NAMES, POLICY_VERSION
from src.api.routers import review_v2
from src.database.example_registry import ExampleRegistry
from src.orchestration.review_store import ReviewStore, fingerprint


def test_auth_and_exact_scholar_author_sequence(tmp_path, monkeypatch):
    """A forged/missing token or stale hash cannot approve an AI draft."""
    path = Path(tmp_path) / "review.db"
    monkeypatch.setattr(review_v2, "SQLITE_DB_PATH", path)
    monkeypatch.setenv("REVIEW_SCHOLAR_TOKEN", "scholar-secret")
    monkeypatch.setenv("REVIEW_AUTHOR_TOKEN", "author-secret")
    store = ReviewStore(path)
    registry = ExampleRegistry(path)
    registry.register("Founder One", "PERSON", "synthetic test provenance")
    content = {"original_sanskrit_verse": "सत्यं कार्यम्", "named_examples": [
        {"name": "Founder One", "polarity": "POSITIVE", "location": "case"}]}
    report = {"policy_version": POLICY_VERSION, "gates": {name: "PASS" for name in GATE_NAMES}}
    version = store.save_draft("one", content, report)
    store.mark_ai_validated("one", version)
    author = review_v2.HumanApproval(kind="AUTHOR", version=version,
                                     content_sha256=fingerprint(content), reviewer_name="Author")
    scholar = review_v2.HumanApproval(kind="SCHOLAR", version=version,
                                      content_sha256=fingerprint(content), reviewer_name="Scholar")
    with pytest.raises(HTTPException) as forbidden:
        review_v2.approve_exact_version("one", author, "wrong")
    assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as conflict:
        review_v2.approve_exact_version("one", author, "author-secret")
    assert conflict.value.status_code == 409
    assert review_v2.approve_exact_version("one", scholar, "scholar-secret")["state"] == "SCHOLAR_REVIEWED"
    with pytest.raises(HTTPException) as missing_examples:
        review_v2.approve_exact_version("one", author, "author-secret")
    assert missing_examples.value.status_code == 409
    assert store.get_version("one", version)["state"] == "SCHOLAR_REVIEWED"
    registry.reserve("one", content["named_examples"], fingerprint(content))
    assert review_v2.approve_exact_version("one", author, "author-secret")["state"] == "AUTHOR_APPROVED"
    registry.verify_manifest([{"unit_id": "one", "content_sha256": fingerprint(content),
                               "content": content}])
